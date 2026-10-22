"""The life of one run sample as a queue job, shared by Explore, Measure and scenario
generation.

A job claims its sample, checks the run's token budget, prepares the work (which
may find that the run's inputs changed), runs it with a heartbeat, and records the
outcome. A failed attempt is retried once and then recorded as failed. When the
last sample of a run ends, the run is closed and becomes read-only.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core.db import session_scope
from agora_core.explore import OPEN, maybe_finish
from agora_core.model_roles import get_model_roles
from agora_core.models import Run, RunSample, RunStatus

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 2
HEARTBEAT_SECONDS = 20
FINISHED = {
    RunStatus.succeeded.value,
    RunStatus.failed.value,
    RunStatus.cancelled.value,
    RunStatus.stopped_at_budget.value,
}


class SampleChanged(RuntimeError):
    """The seed or agent no longer matches what the run recorded. Not worth retrying."""


@dataclass(frozen=True)
class Claim:
    """A sample this job has claimed, with what the work needs from its run."""

    sample_id: uuid.UUID
    run_id: uuid.UUID
    index: int
    epoch: int
    attempts: int
    config: dict[str, Any]
    token_limit: int


class Outcome(Protocol):
    @property
    def usage(self) -> dict[str, dict[str, int]]: ...

    @property
    def tokens(self) -> int: ...

    @property
    def limit_reached(self) -> bool: ...

    @property
    def log_uri(self) -> str | None: ...


class Work[O: Outcome](Protocol):
    async def run(self) -> O:
        """Do the expensive part, outside any database transaction."""
        ...

    async def record(self, db: AsyncSession, outcome: O) -> None:
        """Store what the run produced, in the transaction that closes the sample."""
        ...


# Prepares the work for a claimed sample; raises SampleChanged if the inputs moved.
Plan = Callable[[Claim], Awaitable[Work[Any]]]


async def _heartbeat(sample_id: uuid.UUID) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        try:
            async with session_scope() as db:
                sample = await db.get(RunSample, sample_id)
                if sample is None:
                    return
                sample.heartbeat_at = datetime.now(UTC)
        except DBAPIError:
            return  # the run finished or was cancelled; nothing more to record


async def finish(run_id: uuid.UUID) -> None:
    async with session_scope() as db:
        await maybe_finish(db, run_id)


async def record_failure(sample_id: uuid.UUID, error: BaseException, *, final: bool) -> None:
    async with session_scope() as db:
        sample = await db.get(RunSample, sample_id, with_for_update=True)
        if sample is None:
            return
        run = await db.get(Run, sample.run_id)
        if run is None or run.status not in OPEN:
            return
        sample.status = RunStatus.failed.value if final else RunStatus.queued.value
        sample.error = f"{type(error).__name__}: {error}"[:2000]
        run_id = run.id
    if final:
        await finish(run_id)


async def _claim(sample_id: uuid.UUID) -> Claim | uuid.UUID | None:
    """The claimed sample; or the run's id if the budget is spent; or None if there is
    nothing to do."""
    async with session_scope() as db:
        sample = await db.get(RunSample, sample_id, with_for_update=True)
        if sample is None or sample.status in FINISHED:
            return None
        run = await db.get(Run, sample.run_id, with_for_update=True)
        if run is None or run.status not in OPEN:
            return None
        remaining = run.token_budget - run.tokens_used
        if remaining <= 0:
            sample.status = RunStatus.stopped_at_budget.value
            sample.error = "The run's token budget was used up before this sample started."
            return run.id
        now = datetime.now(UTC)
        sample.status = RunStatus.running.value
        sample.attempts += 1
        sample.heartbeat_at = now
        if run.status == RunStatus.queued.value:
            run.status = RunStatus.running.value
            run.started_at = now
        return Claim(
            sample_id=sample.id,
            run_id=run.id,
            index=sample.sample_index,
            epoch=sample.epoch,
            attempts=sample.attempts,
            config=dict(run.config),
            token_limit=remaining,
        )


async def execute(sample_id: uuid.UUID, plan: Plan) -> None:
    claim = await _claim(sample_id)
    if claim is None:
        return
    if isinstance(claim, uuid.UUID):
        await finish(claim)
        return

    try:
        work = await plan(claim)
    except SampleChanged as error:
        await record_failure(sample_id, error, final=True)
        return

    heartbeat = asyncio.create_task(_heartbeat(sample_id))
    try:
        outcome = await work.run()
    except Exception as error:
        # Inputs that changed under the work will not change back on a retry.
        final = claim.attempts >= MAX_ATTEMPTS or isinstance(error, SampleChanged)
        log.warning("sample %s failed (attempt %s): %s", sample_id, claim.attempts, error)
        await record_failure(sample_id, error, final=final)
        if final:
            return
        raise RuntimeError(f"sample {sample_id} failed; retrying") from error
    finally:
        heartbeat.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat

    roles = get_model_roles()
    async with session_scope() as db:
        sample = await db.get(RunSample, sample_id, with_for_update=True)
        run = await db.get(Run, claim.run_id, with_for_update=True)
        if sample is None or run is None or run.status not in OPEN:
            return
        await work.record(db, outcome)
        sample.status = (
            RunStatus.stopped_at_budget.value
            if outcome.limit_reached
            else RunStatus.succeeded.value
        )
        sample.error = None
        sample.tokens_used = outcome.tokens
        sample.log_uri = outcome.log_uri
        run.tokens_used += outcome.tokens
        run.cost_usd = Decimal(run.cost_usd) + sum(
            (roles.cost_usd(model, u["input"], u["output"]) for model, u in outcome.usage.items()),
            Decimal(0),
        )
    await finish(claim.run_id)
