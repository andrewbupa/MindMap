from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from bench_api.deps import Db, OversightUser
from bench_api.schemas import AuditEventOut, Page
from bench_core.models import AuditEvent

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_events(
    _: OversightUser,
    db: Db,
    cursor: Annotated[int | None, Query(description="Return events older than this ID.")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    target_type: str | None = None,
    target_id: str | None = None,
) -> Page[AuditEventOut]:
    query = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit + 1)
    if cursor is not None:
        query = query.where(AuditEvent.id < cursor)
    if target_type:
        query = query.where(AuditEvent.target_type == target_type)
    if target_id:
        query = query.where(AuditEvent.target_id == target_id)
    events = list((await db.execute(query)).scalars())
    more = len(events) > limit
    events = events[:limit]
    return Page[AuditEventOut](
        items=[AuditEventOut.model_validate(event) for event in events],
        next_cursor=str(events[-1].id) if more and events else None,
    )
