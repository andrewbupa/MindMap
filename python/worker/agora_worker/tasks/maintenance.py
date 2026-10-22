"""Housekeeping that keeps the queue healthy across deploys."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from procrastinate import JobContext
from sqlalchemy import delete

from agora_core.db import session_scope
from agora_core.models import UserSession
from agora_core.queue import app

log = logging.getLogger(__name__)

# A worker that has not sent a heartbeat for this long is presumed dead.
STALLED_AFTER_SECONDS = 60


@app.periodic(cron="* * * * *")
@app.task(name="retry_stalled_jobs", queueing_lock="retry_stalled_jobs", pass_context=True)
async def retry_stalled_jobs(context: JobContext, timestamp: int) -> int:
    """Re-queue jobs left running by a worker that died, such as one killed by a deploy."""
    stalled = list(
        await context.app.job_manager.get_stalled_jobs(
            seconds_since_heartbeat=STALLED_AFTER_SECONDS
        )
    )
    for job in stalled:
        log.warning("re-queueing stalled job %s (%s)", job.id, job.task_name)
        await context.app.job_manager.retry_job(job)
    return len(stalled)


@app.periodic(cron="17 * * * *")
@app.task(name="delete_expired_sessions", queueing_lock="delete_expired_sessions")
async def delete_expired_sessions(timestamp: int) -> None:
    async with session_scope() as db:
        await db.execute(delete(UserSession).where(UserSession.expires_at < datetime.now(UTC)))
