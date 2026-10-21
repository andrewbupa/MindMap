"""Audit events: who launched, reviewed, exported or approved what, and when."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from bench_core.models import AuditEvent


async def record(
    session: AsyncSession,
    action: str,
    *,
    actor_id: uuid.UUID | None,
    target_type: str | None = None,
    target_id: str | uuid.UUID | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        action=action,
        actor_id=actor_id,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        detail=detail or {},
    )
    session.add(event)
    await session.flush()
    return event
