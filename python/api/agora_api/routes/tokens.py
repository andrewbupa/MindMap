"""API tokens for machine clients of the OpenAI-compatible endpoint."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from agora_api.deps import AdminUser, Db
from agora_api.schemas import ApiTokenCreate, ApiTokenCreated, ApiTokenOut
from agora_api.sessions import hash_token
from agora_core import audit
from agora_core.models import ApiToken

router = APIRouter(prefix="/tokens", tags=["tokens"])

TOKEN_PREFIX = "agora_"  # noqa: S105 (a visible prefix, not a secret)


@router.get("")
async def list_tokens(_: AdminUser, db: Db) -> list[ApiTokenOut]:
    rows = (await db.execute(select(ApiToken).order_by(ApiToken.created_at.desc()))).scalars()
    return [ApiTokenOut.model_validate(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_token(body: ApiTokenCreate, admin: AdminUser, db: Db) -> ApiTokenCreated:
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    row = ApiToken(
        name=body.name, token_hash=hash_token(token), prefix=token[:12], created_by=admin.id
    )
    db.add(row)
    await db.flush()
    await audit.record(
        db,
        "api_token.create",
        actor_id=admin.id,
        target_type="api_token",
        target_id=row.id,
        detail={"name": body.name},
    )
    await db.commit()
    return ApiTokenCreated(token=token, details=ApiTokenOut.model_validate(row))


@router.delete("/{token_id}")
async def revoke_token(token_id: uuid.UUID, admin: AdminUser, db: Db) -> ApiTokenOut:
    row = await db.get(ApiToken, token_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such token.")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        await audit.record(
            db, "api_token.revoke", actor_id=admin.id, target_type="api_token", target_id=row.id
        )
        await db.commit()
    return ApiTokenOut.model_validate(row)
