from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bench_core import queue
from bench_core.models import SystemCheck
from bench_core.storage import get_storage
from bench_worker.app import app
from bench_worker.tasks.maintenance import retry_stalled_jobs


async def _run_queued_jobs() -> None:
    async with app.open_async():
        await app.run_worker_async(wait=False, install_signal_handlers=False, listen_notify=False)


async def test_system_check_writes_to_storage_and_records_evidence(
    db: AsyncSession, s3_server: str
) -> None:
    check = SystemCheck(status="queued")
    db.add(check)
    await db.commit()
    async with app.open_async():
        await queue.defer("system_check", check_id=str(check.id))
    await _run_queued_jobs()

    await db.refresh(check)
    assert check.status == "succeeded"
    assert check.object_key == f"system-checks/{check.id}.json"
    assert check.detail["read_back_matches"] is True
    stored = json.loads(get_storage().get_bytes(check.object_key))
    assert stored["check_id"] == str(check.id)
    assert stored["commit"] == "0" * 40

    audit = (await db.execute(text("SELECT action FROM audit_event"))).scalars().all()
    assert "system_check.complete" in audit


async def test_missing_check_is_ignored(db: AsyncSession, s3_server: str) -> None:
    async with app.open_async():
        await queue.defer("system_check", check_id=str(uuid.uuid4()))
    await _run_queued_jobs()
    statuses = (await db.execute(text("SELECT status FROM procrastinate_jobs"))).scalars().all()
    assert "failed" not in statuses


async def test_stalled_jobs_are_requeued(db: AsyncSession) -> None:
    """A job left 'doing' by a worker that stopped sending heartbeats goes back to 'todo'."""
    async with app.open_async():
        job_id = await queue.defer("system_check", check_id=str(uuid.uuid4()))
    worker_id = (
        await db.execute(
            text(
                "INSERT INTO procrastinate_workers (last_heartbeat)"
                " VALUES (now() - interval '10 minutes') RETURNING id"
            )
        )
    ).scalar_one()
    await db.execute(
        text("UPDATE procrastinate_jobs SET status = 'doing', worker_id = :w WHERE id = :j"),
        {"w": worker_id, "j": job_id},
    )
    await db.commit()

    async with app.open_async():
        context = SimpleNamespace(app=app)
        requeued = await retry_stalled_jobs.func(context, timestamp=0)  # type: ignore[arg-type]
    assert requeued == 1
    status = (
        await db.execute(text("SELECT status FROM procrastinate_jobs WHERE id = :j"), {"j": job_id})
    ).scalar_one()
    assert status == "todo"
