from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bench_api.auth import identity_from_claims, resolve_roles, safe_next
from bench_api.sessions import COOKIE_NAME
from bench_core.config import Settings
from bench_core.models import AuditEvent, User, UserSession
from testsupport.oidc import FakeOIDCClient, sign_in_as


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "/"),
        ("/lens?run=1", "/lens?run=1"),
        ("https://evil.example", "/"),
        ("//evil.example", "/"),
        ("/\\evil.example", "/"),
        ("lens", "/"),
    ],
)
def test_safe_next_allows_only_same_site_paths(value: str | None, expected: str) -> None:
    assert safe_next(value) == expected


def test_roles_follow_idp_groups_when_a_map_is_set() -> None:
    settings = Settings(oidc_role_map={"g-review": "reviewer", "g-x": "not-a-role"})
    claims = {"email": "a@example.test", "groups": ["g-review", "g-x", "other"]}
    assert resolve_roles(["author"], claims, settings) == ["reviewer"]


def test_roles_are_left_alone_without_a_map() -> None:
    settings = Settings(oidc_role_map={})
    assert resolve_roles(["author"], {"email": "a@example.test"}, settings) == ["author"]


def test_bootstrap_admins_are_admins() -> None:
    settings = Settings(bootstrap_admins="Boss@Example.test", oidc_role_map={})
    assert resolve_roles([], {"email": "boss@example.test"}, settings) == ["admin"]


def test_identity_needs_issuer_subject_and_email() -> None:
    with pytest.raises(Exception, match="issuer, subject and email"):
        identity_from_claims({"iss": "x", "sub": "y"})
    assert identity_from_claims(
        {"iss": "i", "sub": "s", "preferred_username": "Pat@Example.test"}
    ) == ("i", "s", "pat@example.test", "pat@example.test")


async def test_sign_in_creates_user_session_and_audit(
    client: httpx.AsyncClient, idp: FakeOIDCClient, db: AsyncSession
) -> None:
    response = await sign_in_as(client, idp, "admin@example.test")
    assert response.status_code == 303
    assert response.headers["location"] == "/explore"
    cookie = response.cookies.get(COOKIE_NAME)
    assert cookie and len(cookie) > 30
    set_cookie = response.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie

    me = (await client.get("/api/me")).json()
    assert me["email"] == "admin@example.test"
    assert me["roles"] == ["admin"]

    stored = (await db.execute(select(UserSession))).scalar_one()
    assert stored.token_hash != cookie
    actions = (await db.execute(select(AuditEvent.action))).scalars().all()
    assert "auth.sign_in" in actions and "user.roles_changed" in actions


async def test_signed_out_requests_are_refused(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/me")).status_code == 401
    client.cookies.set(COOKIE_NAME, "not-a-real-token")
    assert (await client.get("/api/me")).status_code == 401


async def test_expired_sessions_are_refused(
    client: httpx.AsyncClient, idp: FakeOIDCClient, db: AsyncSession
) -> None:
    await sign_in_as(client, idp, "pat@example.test")
    await db.execute(
        update(UserSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await db.commit()
    assert (await client.get("/api/me")).status_code == 401


async def test_role_checks(client: httpx.AsyncClient, idp: FakeOIDCClient) -> None:
    await sign_in_as(client, idp, "author@example.test")
    assert (await client.get("/api/me")).json()["roles"] == []
    assert (await client.get("/api/users")).status_code == 403
    assert (await client.get("/api/audit")).status_code == 403


async def test_writes_need_the_csrf_header(client: httpx.AsyncClient, idp: FakeOIDCClient) -> None:
    await sign_in_as(client, idp, "admin@example.test")
    response = await client.patch(
        "/api/me", json={"sensitive_opt_in": True}, headers={"x-bench-request": ""}
    )
    assert response.status_code == 403
    response = await client.patch("/api/me", json={"sensitive_opt_in": True})
    assert response.status_code == 200 and response.json()["sensitive_opt_in"] is True


async def test_admin_manages_roles_but_not_their_own_admin(
    client: httpx.AsyncClient, idp: FakeOIDCClient, db: AsyncSession
) -> None:
    await sign_in_as(client, idp, "reviewer@example.test")
    await sign_in_as(client, idp, "admin@example.test")
    users = {user["email"]: user for user in (await client.get("/api/users")).json()}

    reviewer_id = users["reviewer@example.test"]["id"]
    response = await client.patch(f"/api/users/{reviewer_id}", json={"roles": ["reviewer"]})
    assert response.status_code == 200 and response.json()["roles"] == ["reviewer"]

    admin_id = users["admin@example.test"]["id"]
    response = await client.patch(f"/api/users/{admin_id}", json={"roles": ["author"]})
    assert response.status_code == 409

    response = await client.patch(f"/api/users/{reviewer_id}", json={"is_active": False})
    assert response.status_code == 200
    reviewer = await db.get(User, reviewer_id)
    assert reviewer is not None
    sessions = (
        await db.execute(select(UserSession).where(UserSession.user_id == reviewer.id))
    ).all()
    assert sessions == []

    events = (await client.get("/api/audit", params={"target_id": reviewer_id})).json()
    assert {event["action"] for event in events["items"]} >= {
        "user.roles_changed",
        "user.active_changed",
    }


async def test_sign_out_ends_the_session(client: httpx.AsyncClient, idp: FakeOIDCClient) -> None:
    await sign_in_as(client, idp, "pat@example.test")
    response = await client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json()["redirect"].startswith("https://idp.example.test/logout?")
    assert "id_token_hint=fake-id-token" in response.json()["redirect"]
    assert (await client.get("/api/me")).status_code == 401


async def test_an_email_held_by_another_identity_is_refused(
    client: httpx.AsyncClient, idp: FakeOIDCClient, db: AsyncSession
) -> None:
    await sign_in_as(client, idp, "admin@example.test")
    refused = await sign_in_as(client, idp, "admin@example.test", sub="someone-else")
    assert refused.status_code == 409 and "another sign-in identity" in refused.text
    events = (
        (await db.execute(select(AuditEvent).where(AuditEvent.action == "auth.refused")))
        .scalars()
        .all()
    )
    assert [e.detail["reason"] for e in events] == ["email_held_by_another_identity"]
