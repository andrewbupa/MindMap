from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from bench_api.deps import AdminUser, Db
from bench_api.schemas import UserOut, UserUpdate
from bench_api.sessions import end_all_sessions
from bench_core import audit
from bench_core.models import Role, User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
async def list_users(_: AdminUser, db: Db) -> list[UserOut]:
    users = (await db.execute(select(User).order_by(func.lower(User.name)))).scalars()
    return [UserOut.model_validate(user) for user in users]


@router.patch("/{user_id}")
async def update_user(user_id: uuid.UUID, body: UserUpdate, admin: AdminUser, db: Db) -> UserOut:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such user.")
    if user.id == admin.id and (
        body.is_active is False or (body.roles is not None and Role.admin not in body.roles)
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "You cannot remove your own admin role or deactivate yourself.",
        )
    if body.roles is not None:
        before, after = sorted(user.roles), sorted({role.value for role in body.roles})
        if before != after:
            user.roles = after
            await audit.record(
                db,
                "user.roles_changed",
                actor_id=admin.id,
                target_type="user",
                target_id=user.id,
                detail={"before": before, "after": after, "by": "admin"},
            )
    if body.is_active is not None and body.is_active != user.is_active:
        user.is_active = body.is_active
        if not body.is_active:
            await end_all_sessions(db, user)
        await audit.record(
            db,
            "user.active_changed",
            actor_id=admin.id,
            target_type="user",
            target_id=user.id,
            detail={"is_active": body.is_active},
        )
    await db.commit()
    return UserOut.model_validate(user)
