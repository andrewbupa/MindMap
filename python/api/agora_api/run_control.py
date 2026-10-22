"""Following and cancelling runs made of sample jobs: Inquiry, Tally and scenario sets."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import HTTPException, status
from fastapi.sse import ServerSentEvent
from sqlalchemy.ext.asyncio import AsyncSession

from agora_api.schemas import RunOut
from agora_core import audit, inquiry
from agora_core.db import get_sessionmaker
from agora_core.models import Role, Run, RunStatus, User

# App Platform closes requests after 100 seconds; clients reconnect after each stream.
STREAM_SECONDS = 85
POLL_SECONDS = 2.0


async def status_events(run_id: uuid.UUID) -> AsyncIterator[ServerSentEvent]:
    """Sample counts as they change, until the run finishes or the stream times out."""
    last: dict[str, object] | None = None
    for _tick in range(int(STREAM_SECONDS / POLL_SECONDS)):
        async with get_sessionmaker()() as fresh:
            run = await fresh.get(Run, run_id)
            if run is None:
                return
            state: dict[str, object] = {
                "status": run.status,
                "tokens_used": run.tokens_used,
                "counts": await inquiry.sample_counts(fresh, run_id),
            }
        if state != last:
            last = state
            yield ServerSentEvent(data=state, event="status", retry=3000)
        if state["status"] not in inquiry.OPEN:
            return
        await asyncio.sleep(POLL_SECONDS)


async def cancel_run(run: Run, user: User, db: AsyncSession) -> RunOut:
    """Stop a run: queued samples never start, and running ones are not recorded."""
    if run.launched_by != user.id and not user.has_role(Role.admin):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the person who launched this can cancel it."
        )
    if run.status not in inquiry.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, "This run has already finished.")
    run.status = RunStatus.cancelled.value
    run.finished_at = datetime.now(UTC)
    await audit.record(db, "run.cancel", actor_id=user.id, target_type="run", target_id=run.id)
    await db.commit()
    return RunOut.model_validate(run)
