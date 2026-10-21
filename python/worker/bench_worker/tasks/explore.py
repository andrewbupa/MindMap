"""The Explore sample job. One job per seed and epoch; see bench_core.explore."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from procrastinate import RetryStrategy
from sqlalchemy.exc import DBAPIError

from bench_core.agents.load import load_agent_version
from bench_core.config import get_settings
from bench_core.db import session_scope
from bench_core.explore import OPEN, maybe_finish
from bench_core.model_roles import get_model_roles
from bench_core.models import Run, RunSample, RunStatus
from bench_core.queue import RUNS_QUEUE, app
from bench_core.seeds import load_seeds, scenario_for
from bench_core.storage import Storage, get_storage
from bench_worker.explore.indexing import index_sample
from bench_worker.explore.runner import ModelFactory, default_models, run_audit

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


@app.task(
    name="explore_sample",
    queue=RUNS_QUEUE,
    retry=RetryStrategy(max_attempts=MAX_ATTEMPTS, wait=30, retry_exceptions={RuntimeError}),
)
async def explore_sample(run_sample_id: str) -> None:
    await execute_sample(uuid.UUID(run_sample_id))


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


async def _finish(run_id: uuid.UUID) -> None:
    async with session_scope() as db:
        await maybe_finish(db, run_id)


async def _record_failure(sample_id: uuid.UUID, error: BaseException, *, final: bool) -> None:
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
        await _finish(run_id)


async def execute_sample(
    sample_id: uuid.UUID,
    *,
    models: ModelFactory = default_models,
    storage: Storage | None = None,
) -> None:
    settings = get_settings()
    roles = get_model_roles()
    storage = storage or get_storage()

    async with session_scope() as db:
        sample = await db.get(RunSample, sample_id, with_for_update=True)
        if sample is None or sample.status in FINISHED:
            return
        run = await db.get(Run, sample.run_id, with_for_update=True)
        if run is None or run.status not in OPEN:
            return
        run_id = run.id
        remaining = run.token_budget - run.tokens_used
        if remaining <= 0:
            sample.status = RunStatus.stopped_at_budget.value
            sample.error = "The run's token budget was used up before this sample started."
            stopped = True
        else:
            stopped = False
            now = datetime.now(UTC)
            sample.status = RunStatus.running.value
            sample.attempts += 1
            sample.heartbeat_at = now
            if run.status == RunStatus.queued.value:
                run.status = RunStatus.running.value
                run.started_at = now
            attempts, index, epoch = sample.attempts, sample.sample_index, sample.epoch
            config = dict(run.config)
            stored = await load_agent_version(db, config["agent"], config["version"])
    if stopped:
        await _finish(run_id)
        return

    try:
        if stored.prompt.sha256 != config["prompt_sha"]:
            raise SampleChanged("the prompt version no longer matches the run")
        if stored.tool_profile.sha256 != config["tool_profile_sha"]:
            raise SampleChanged("the agent's tools changed after the run was launched")
        key = config["seeds"][index]
        seed = load_seeds(settings.repo_root).get(key)
        if seed is None or seed.sha256 != config["seed_shas"][key]:
            raise SampleChanged(f"seed {key} changed after the run was launched")
    except SampleChanged as error:
        await _record_failure(sample_id, error, final=True)
        return

    heartbeat = asyncio.create_task(_heartbeat(sample_id))
    try:
        outcome = await run_audit(
            run_id=str(run_id),
            index=index,
            epoch=epoch,
            seed=seed,
            version=stored.adapter_input(),
            display_name=stored.agent.name,
            config=config,
            root=settings.repo_root,
            storage=storage,
            token_limit=remaining,
            models=models,
        )
    except Exception as error:
        final = attempts >= MAX_ATTEMPTS
        log.warning("explore sample %s failed (attempt %s): %s", sample_id, attempts, error)
        await _record_failure(sample_id, error, final=final)
        if final:
            return
        raise RuntimeError(f"sample {sample_id} failed; retrying") from error
    finally:
        heartbeat.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat

    async with session_scope() as db:
        sample = await db.get(RunSample, sample_id, with_for_update=True)
        run = await db.get(Run, run_id, with_for_update=True)
        if sample is None or run is None or run.status not in OPEN:
            return
        scenario = await scenario_for(db, seed)
        await index_sample(
            db,
            run_id=run_id,
            scenario_id=scenario.id,
            sample_index=index,
            epoch=epoch,
            sample=outcome.sample,
            log_uri=outcome.log_uri,
            judge_model=config["models"]["judge"],
        )
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
    await _finish(run_id)
