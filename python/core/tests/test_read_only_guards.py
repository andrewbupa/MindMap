"""Finished runs, everything under them, and the audit log refuse changes in Postgres."""

import uuid

import pytest
from sqlalchemy import delete, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from bench_core import audit
from bench_core.models import AuditEvent, Message, Run, RunStatus, Score, Transcript


def _run(**overrides: object) -> Run:
    values: dict[str, object] = {
        "kind": "explore",
        "config": {"k": 1},
        "config_hash": "0" * 64,
        "git_commit": "abc",
        "model_ids": {"target": "model-a"},
        "token_budget": 1000,
    }
    values.update(overrides)
    return Run(**values)


async def _finished_run_with_transcript(db: AsyncSession) -> tuple[Run, Transcript]:
    run = _run()
    db.add(run)
    await db.flush()
    transcript = Transcript(run_id=run.id, sample_index=0, log_uri="s3://b/k")
    db.add(transcript)
    await db.flush()
    db.add(Message(transcript_id=transcript.id, index=0, role="assistant", content="Hello"))
    db.add(
        Score(
            transcript_id=transcript.id,
            source="petri_judge",
            dimension="d",
            value=1,
            scale_max=10,
        )
    )
    # Children are written before the run is marked finished; afterwards the guard bites.
    await db.flush()
    run.status = RunStatus.succeeded.value
    await db.commit()
    return run, transcript


async def test_running_run_can_change(db: AsyncSession) -> None:
    run = _run()
    db.add(run)
    await db.commit()
    await db.execute(update(Run).where(Run.id == run.id).values(status="running"))
    await db.commit()


async def test_finished_run_refuses_update_and_delete(db: AsyncSession) -> None:
    run, _ = await _finished_run_with_transcript(db)
    run_id = run.id
    with pytest.raises(DBAPIError, match="finished and read-only"):
        await db.execute(update(Run).where(Run.id == run_id).values(title="edited"))
    await db.rollback()
    with pytest.raises(DBAPIError, match="finished and read-only"):
        await db.execute(delete(Run).where(Run.id == run_id))
    await db.rollback()


async def test_children_of_finished_run_refuse_changes(db: AsyncSession) -> None:
    run, transcript = await _finished_run_with_transcript(db)
    run_id, transcript_id = run.id, transcript.id
    statements = [
        update(Transcript).where(Transcript.id == transcript_id).values(summary="x"),
        update(Message).where(Message.transcript_id == transcript_id).values(content="x"),
        delete(Score).where(Score.transcript_id == transcript_id),
    ]
    for statement in statements:
        with pytest.raises(DBAPIError, match="belongs to a finished run"):
            await db.execute(statement)
        await db.rollback()

    db.add(Message(transcript_id=transcript_id, index=1, role="user", content="late"))
    with pytest.raises(DBAPIError, match="belongs to a finished run"):
        await db.flush()
    await db.rollback()

    db.add(Transcript(run_id=run_id, sample_index=1, log_uri="s3://b/k2"))
    with pytest.raises(DBAPIError, match="belongs to a finished run"):
        await db.flush()
    await db.rollback()


async def test_moving_a_child_into_a_finished_run_is_refused(db: AsyncSession) -> None:
    finished, _ = await _finished_run_with_transcript(db)
    finished_id = finished.id
    open_run = _run()
    db.add(open_run)
    await db.flush()
    stray = Transcript(run_id=open_run.id, sample_index=0, log_uri="s3://b/k3")
    db.add(stray)
    await db.commit()
    with pytest.raises(DBAPIError, match="belongs to a finished run"):
        await db.execute(
            update(Transcript).where(Transcript.id == stray.id).values(run_id=finished_id)
        )
    await db.rollback()


async def test_audit_log_is_append_only(db: AsyncSession) -> None:
    event = await audit.record(
        db, "run.launch", actor_id=None, target_type="run", target_id=uuid.uuid4()
    )
    await db.commit()
    with pytest.raises(DBAPIError, match="append-only"):
        await db.execute(
            update(AuditEvent).where(AuditEvent.id == event.id).values(action="edited")
        )
    await db.rollback()
    with pytest.raises(DBAPIError, match="append-only"):
        await db.execute(text("DELETE FROM audit_event"))
    await db.rollback()
