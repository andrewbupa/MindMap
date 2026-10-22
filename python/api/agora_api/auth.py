"""Single sign-on with OpenID Connect (authorisation code flow with PKCE).

Authlib keeps state, nonce and the PKCE verifier in a short-lived signed cookie
(``agora_oauth``). Once the identity provider returns, we create a server-side
session and set ``agora_session``, an HTTP-only cookie scoped to the whole site.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any
from urllib.parse import urlencode

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select

from agora_api.deps import AppSettings, Db
from agora_api.sessions import COOKIE_NAME, create_session, end_session
from agora_core import audit
from agora_core.config import Settings, get_settings
from agora_core.models import Role, User

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

VALID_ROLES = {role.value for role in Role}


@lru_cache
def get_oauth() -> OAuth:
    settings = get_settings()
    oauth = OAuth()
    oauth.register(
        name="agora",
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret.get_secret_value(),
        server_metadata_url=settings.oidc_metadata_url,
        client_kwargs={"scope": settings.oidc_scopes, "code_challenge_method": "S256"},
    )
    return oauth


def safe_next(value: str | None) -> str:
    """Only same-site paths are allowed as a post-sign-in destination."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    return value


def _groups(claims: dict[str, Any], claim: str) -> list[str]:
    value = claims.get(claim) or []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value] if isinstance(value, Iterable) else []


def resolve_roles(existing: list[str], claims: dict[str, Any], settings: Settings) -> list[str]:
    """Work out a user's roles at sign-in.

    With a group-to-role map configured, the identity provider is the source of
    truth and roles follow its groups on every sign-in. Without one, roles are
    granted inside Agora by an admin and sign-in leaves them alone. Either way,
    emails listed in AGORA_BOOTSTRAP_ADMINS are admins.
    """
    if settings.oidc_role_map:
        roles = {
            settings.oidc_role_map[group]
            for group in _groups(claims, settings.oidc_groups_claim)
            if group in settings.oidc_role_map
        }
    else:
        roles = set(existing)
    email = str(claims.get("email") or "").lower()
    if email and email in settings.bootstrap_admins:
        roles.add(Role.admin.value)
    return sorted(role for role in roles if role in VALID_ROLES)


def identity_from_claims(claims: dict[str, Any]) -> tuple[str, str, str, str]:
    issuer = str(claims.get("iss") or "")
    subject = str(claims.get("sub") or "")
    email = str(claims.get("email") or claims.get("preferred_username") or "").strip().lower()
    if not issuer or not subject or "@" not in email:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Your identity provider did not send an issuer, subject and email address.",
        )
    name = str(claims.get("name") or email)
    return issuer, subject, email, name


async def sign_in(
    db: Db, claims: dict[str, Any], settings: Settings
) -> tuple[User, list[str], list[str]]:
    issuer, subject, email, name = identity_from_claims(claims)
    user = (
        await db.execute(
            select(User).where(User.oidc_issuer == issuer, User.oidc_subject == subject)
        )
    ).scalar_one_or_none()
    holder = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if holder is not None and holder is not user:
        # Never relink an account by email: whoever can change their address at the
        # identity provider could otherwise sign in as someone else.
        await audit.record(
            db,
            "auth.refused",
            actor_id=None,
            target_type="user",
            target_id=holder.id,
            detail={
                "reason": "email_held_by_another_identity",
                "issuer": issuer,
                "subject": subject,
            },
        )
        await db.commit()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "That email address belongs to another sign-in identity. Ask an admin to check"
            " your account.",
        )
    before: list[str] = []
    if user is None:
        user = User(email=email, name=name, oidc_issuer=issuer, oidc_subject=subject, roles=[])
        db.add(user)
    else:
        before = list(user.roles)
        user.email, user.name = email, name
    user.roles = resolve_roles(before, {**claims, "email": email}, settings)
    user.last_seen_at = datetime.now(UTC)
    await db.flush()
    return user, before, list(user.roles)


@router.get("/login", include_in_schema=False)
async def login(request: Request, settings: AppSettings, next: str | None = None) -> Response:
    request.session["next"] = safe_next(next)
    client = get_oauth().create_client("agora")
    redirect_uri = f"{settings.public_url.rstrip('/')}/api/auth/callback"
    response: Response = await client.authorize_redirect(request, redirect_uri)
    return response


@router.get("/callback", include_in_schema=False)
async def callback(request: Request, db: Db, settings: AppSettings) -> Response:
    client = get_oauth().create_client("agora")
    try:
        token = await client.authorize_access_token(request)
    except OAuthError as error:
        log.warning("sign-in failed: %s", error.error)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sign-in did not complete.") from error
    claims = dict(token.get("userinfo") or {})
    user, before, after = await sign_in(db, claims, settings)
    session_token = await create_session(
        db,
        user,
        settings,
        id_token=token.get("id_token"),
        user_agent=request.headers.get("user-agent"),
    )
    await audit.record(db, "auth.sign_in", actor_id=user.id, target_type="user", target_id=user.id)
    if before != after:
        await audit.record(
            db,
            "user.roles_changed",
            actor_id=None,
            target_type="user",
            target_id=user.id,
            detail={"before": before, "after": after, "by": "sign_in"},
        )
    await db.commit()

    destination = safe_next(request.session.pop("next", None))
    response = RedirectResponse(destination, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        COOKIE_NAME,
        session_token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )
    return response


class SignOutOut(BaseModel):
    redirect: str


@router.post("/logout")
async def logout(request: Request, response: Response, db: Db, settings: AppSettings) -> SignOutOut:
    token = request.cookies.get(COOKIE_NAME)
    redirect = "/signed-out"
    if token:
        ended = await end_session(db, token)
        if ended is not None:
            await audit.record(
                db,
                "auth.sign_out",
                actor_id=ended.user_id,
                target_type="user",
                target_id=ended.user_id,
            )
            redirect = await _end_session_url(ended.id_token_hint, settings) or redirect
        await db.commit()
    response.delete_cookie(COOKIE_NAME, path="/", secure=settings.secure_cookies, samesite="lax")
    return SignOutOut(redirect=redirect)


async def _end_session_url(id_token: str | None, settings: Settings) -> str | None:
    try:
        metadata = await get_oauth().create_client("agora").load_server_metadata()
    except Exception:  # the identity provider being down must not block signing out
        log.warning("could not load identity provider metadata for sign-out")
        return None
    endpoint = metadata.get("end_session_endpoint")
    if not endpoint:
        return None
    params = {"post_logout_redirect_uri": f"{settings.public_url.rstrip('/')}/signed-out"}
    if id_token:
        params["id_token_hint"] = id_token
    params["client_id"] = settings.oidc_client_id
    return f"{endpoint}?{urlencode(params)}"
