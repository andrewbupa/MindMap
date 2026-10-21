"""Request dependencies: database sessions, the signed-in user, and role checks."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from bench_api.sessions import COOKIE_NAME, user_for_token
from bench_core.config import Settings, get_settings
from bench_core.db import get_sessionmaker
from bench_core.models import Role, User


async def get_db() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


Db = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


async def current_user(request: Request, db: Db) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    found = await user_for_token(db, token)
    if found is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has ended.")
    user, _ = found
    request.state.user_id = user.id
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_role(*roles: Role) -> Callable[..., Coroutine[Any, Any, User]]:
    """Allow users holding any of ``roles``. Admins pass every check."""

    async def check(user: CurrentUser) -> User:
        if not user.has_role(*roles):
            needed = " or ".join(role.value for role in roles)
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"This needs the {needed} role.")
        return user

    return check


AdminUser = Annotated[User, Depends(require_role(Role.admin))]
OversightUser = Annotated[User, Depends(require_role(Role.compliance))]
