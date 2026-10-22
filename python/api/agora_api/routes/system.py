"""System checks: an admin sends a job through queue, worker and storage, then sees the evidence."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy import select

from agora_api.deps import AdminUser, Db
from agora_api.schemas import SignedUrlOut, SystemCheckOut
from agora_core import audit, queue
from agora_core.db import get_sessionmaker
from agora_core.models import SystemCheck
from agora_core.storage import get_storage

router = APIRouter(prefix="/system/checks", tags=["system"])

FINISHED = {"succeeded", "failed"}
# App Platform's edge closes requests after 100 seconds; end streams before that.
STREAM_SECONDS = 85
POLL_SECONDS = 1.0


@router.post("", status_code=status.HTTP_201_CREATED)
async def launch_check(admin: AdminUser, db: Db) -> SystemCheckOut:
    check = SystemCheck(requested_by=admin.id, status="queued")
    db.add(check)
    await db.flush()
    await audit.record(
        db, "system_check.launch", actor_id=admin.id, target_type="system_check", target_id=check.id
    )
    await db.commit()
    check.job_id = await queue.defer("system_check", check_id=str(check.id))
    await db.commit()
    return SystemCheckOut.model_validate(check)


@router.get("")
async def list_checks(_: AdminUser, db: Db) -> list[SystemCheckOut]:
    checks = (
        await db.execute(select(SystemCheck).order_by(SystemCheck.created_at.desc()).limit(20))
    ).scalars()
    return [SystemCheckOut.model_validate(check) for check in checks]


async def _get(db: Db, check_id: uuid.UUID) -> SystemCheck:
    check = await db.get(SystemCheck, check_id)
    if check is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such system check.")
    return check


@router.get("/{check_id}")
async def read_check(check_id: uuid.UUID, _: AdminUser, db: Db) -> SystemCheckOut:
    return SystemCheckOut.model_validate(await _get(db, check_id))


@router.get("/{check_id}/events", response_class=EventSourceResponse)
async def stream_check(check_id: uuid.UUID, _: AdminUser, db: Db) -> AsyncIterator[ServerSentEvent]:
    """Status updates as server-sent events. Clients reconnect, or fall back to polling."""
    await _get(db, check_id)
    last: str | None = None
    for _tick in range(int(STREAM_SECONDS / POLL_SECONDS)):
        async with get_sessionmaker()() as fresh:
            check = await fresh.get(SystemCheck, check_id)
        if check is None:
            return
        body = SystemCheckOut.model_validate(check)
        if body.status != last:
            last = body.status
            yield ServerSentEvent(data=body.model_dump(mode="json"), event="status", retry=2000)
        if body.status in FINISHED:
            return
        await asyncio.sleep(POLL_SECONDS)


@router.get("/{check_id}/object")
async def check_object(check_id: uuid.UUID, admin: AdminUser, db: Db) -> SignedUrlOut:
    """A short-lived link to the object the worker wrote: the evidence behind the check."""
    check = await _get(db, check_id)
    if not check.object_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This check has not written an object yet.")
    storage = get_storage()
    await audit.record(
        db,
        "storage.signed_url",
        actor_id=admin.id,
        target_type="system_check",
        target_id=check.id,
        detail={"key": check.object_key},
    )
    await db.commit()
    return SignedUrlOut(
        url=storage.signed_url(check.object_key), expires_in=storage.signed_url_seconds
    )
