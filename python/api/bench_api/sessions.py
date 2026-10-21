"""Server-side sessions. The browser holds a random token; Postgres holds its SHA-256."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bench_core.config import Settings
from bench_core.models import User, UserSession

COOKIE_NAME = "bench_session"
TOUCH_INTERVAL = timedelta(minutes=5)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


async def create_session(
    db: AsyncSession,
    user: User,
    settings: Settings,
    *,
    id_token: str | None,
    user_agent: str | None,
) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db.add(
        UserSession(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=now + timedelta(hours=settings.session_hours),
            last_seen_at=now,
            id_token_hint=id_token,
            user_agent=(user_agent or "")[:500] or None,
        )
    )
    await db.flush()
    return token


async def user_for_token(db: AsyncSession, token: str) -> tuple[User, UserSession] | None:
    now = datetime.now(UTC)
    row = (
        await db.execute(
            select(User, UserSession)
            .join(UserSession, UserSession.user_id == User.id)
            .where(UserSession.token_hash == hash_token(token))
        )
    ).first()
    if row is None:
        return None
    user, session = row
    if session.expires_at <= now or not user.is_active:
        await db.delete(session)
        await db.commit()
        return None
    if now - session.last_seen_at > TOUCH_INTERVAL:
        session.last_seen_at = now
        user.last_seen_at = now
        await db.commit()
    return user, session


async def end_session(db: AsyncSession, token: str) -> UserSession | None:
    session = await db.get(UserSession, hash_token(token))
    if session is not None:
        await db.delete(session)
        await db.flush()
    return session


async def end_all_sessions(db: AsyncSession, user: User) -> None:
    await db.execute(delete(UserSession).where(UserSession.user_id == user.id))
