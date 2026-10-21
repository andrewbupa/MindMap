from __future__ import annotations

from fastapi import APIRouter

from bench_api.deps import CurrentUser, Db
from bench_api.schemas import MeOut, MeUpdate
from bench_core import audit

router = APIRouter(prefix="/me", tags=["me"])


@router.get("")
async def read_me(user: CurrentUser) -> MeOut:
    return MeOut.model_validate(user)


@router.patch("")
async def update_me(body: MeUpdate, user: CurrentUser, db: Db) -> MeOut:
    if body.sensitive_opt_in != user.sensitive_opt_in:
        user.sensitive_opt_in = body.sensitive_opt_in
        await audit.record(
            db,
            "user.sensitive_opt_in",
            actor_id=user.id,
            target_type="user",
            target_id=user.id,
            detail={"opt_in": body.sensitive_opt_in},
        )
        await db.commit()
    return MeOut.model_validate(user)
