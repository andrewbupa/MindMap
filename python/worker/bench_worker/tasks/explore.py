"""The Explore sample job. One job per seed and epoch; see bench_core.explore."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from procrastinate import RetryStrategy
from sqlalchemy.ext.asyncio import AsyncSession

from bench_core.agents.load import StoredAgentVersion, load_agent_version
from bench_core.config import get_settings
from bench_core.db import session_scope
from bench_core.queue import RUNS_QUEUE, app
from bench_core.seeds import Seed, load_seeds, scenario_for
from bench_core.storage import Storage, get_storage
from bench_worker.explore.indexing import index_sample
from bench_worker.explore.runner import ModelFactory, SampleOutcome, default_models, run_audit
from bench_worker.samples import MAX_ATTEMPTS, Claim, SampleChanged, execute

__all__ = ["MAX_ATTEMPTS", "SampleChanged", "execute_sample", "explore_sample"]


@app.task(
    name="explore_sample",
    queue=RUNS_QUEUE,
    retry=RetryStrategy(max_attempts=MAX_ATTEMPTS, wait=30, retry_exceptions={RuntimeError}),
)
async def explore_sample(run_sample_id: str) -> None:
    await execute_sample(uuid.UUID(run_sample_id))


async def checked_agent_version(config: dict[str, Any]) -> StoredAgentVersion:
    """The run's agent version, refusing one whose prompt or tools changed since launch."""
    async with session_scope() as db:
        stored = await load_agent_version(db, config["agent"], config["version"])
    if stored.prompt.sha256 != config["prompt_sha"]:
        raise SampleChanged("the prompt version no longer matches the run")
    if stored.tool_profile.sha256 != config["tool_profile_sha"]:
        raise SampleChanged("the agent's tools changed after the run was launched")
    return stored


@dataclass
class ExploreWork:
    claim: Claim
    stored: StoredAgentVersion
    seed: Seed
    root: Path
    storage: Storage
    models: ModelFactory

    async def run(self) -> SampleOutcome:
        return await run_audit(
            run_id=str(self.claim.run_id),
            index=self.claim.index,
            epoch=self.claim.epoch,
            seed=self.seed,
            version=self.stored.adapter_input(),
            display_name=self.stored.agent.name,
            config=self.claim.config,
            root=self.root,
            storage=self.storage,
            token_limit=self.claim.token_limit,
            models=self.models,
        )

    async def record(self, db: AsyncSession, outcome: SampleOutcome) -> None:
        scenario = await scenario_for(db, self.seed)
        await index_sample(
            db,
            run_id=self.claim.run_id,
            scenario_id=scenario.id,
            sample_index=self.claim.index,
            epoch=self.claim.epoch,
            sample=outcome.sample,
            log_uri=outcome.log_uri,
            judge_model=self.claim.config["models"]["judge"],
        )


async def execute_sample(
    sample_id: uuid.UUID,
    *,
    models: ModelFactory = default_models,
    storage: Storage | None = None,
) -> None:
    settings = get_settings()

    async def plan(claim: Claim) -> ExploreWork:
        stored = await checked_agent_version(claim.config)
        key = claim.config["seeds"][claim.index]
        seed = load_seeds(settings.repo_root).get(key)
        if seed is None or seed.sha256 != claim.config["seed_shas"][key]:
            raise SampleChanged(f"seed {key} changed after the run was launched")
        return ExploreWork(
            claim=claim,
            stored=stored,
            seed=seed,
            root=settings.repo_root,
            storage=storage or get_storage(),
            models=models,
        )

    await execute(sample_id, plan)
