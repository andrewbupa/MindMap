"""Measure jobs: scenario generation (one job per generation run) and rollouts (one job
per scenario and repetition). See bench_core.measure.suites."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from inspect_ai.model import Model
from petri_bloom import Behavior
from procrastinate import RetryStrategy
from sqlalchemy.ext.asyncio import AsyncSession

from bench_core.agents.load import StoredAgentVersion
from bench_core.config import get_settings
from bench_core.db import session_scope
from bench_core.measure.behaviours import BehaviourError, BehaviourSource, load_behaviours
from bench_core.measure.suites import (
    SCORE_SOURCE,
    MeasureError,
    scenario_ids,
    scenario_row,
    scenario_set_definition,
    store_scenario_set,
)
from bench_core.models import Behaviour, Run, ScenarioSet
from bench_core.provenance import sha256_text
from bench_core.queue import RUNS_QUEUE, app
from bench_core.storage import Storage, get_storage
from bench_worker.explore.indexing import index_sample
from bench_worker.explore.runner import ModelFactory, SampleOutcome, default_models
from bench_worker.measure.generation import GenerationOutcome, generate_scenarios
from bench_worker.measure.runner import run_rollout
from bench_worker.samples import MAX_ATTEMPTS, Claim, SampleChanged, execute
from bench_worker.tasks.explore import checked_agent_version

RETRY = RetryStrategy(max_attempts=MAX_ATTEMPTS, wait=30, retry_exceptions={RuntimeError})


@app.task(name="generate_scenarios", queue=RUNS_QUEUE, retry=RETRY)
async def generate_scenarios_job(run_sample_id: str) -> None:
    await execute_generation(uuid.UUID(run_sample_id))


@app.task(name="measure_sample", queue=RUNS_QUEUE, retry=RETRY)
async def measure_sample(run_sample_id: str) -> None:
    await execute_measure_sample(uuid.UUID(run_sample_id))


@dataclass
class GenerationWork:
    claim: Claim
    source: BehaviourSource
    behaviour: Behaviour
    model: Model

    async def run(self) -> GenerationOutcome:
        return await generate_scenarios(self.source.definition, self.model)

    async def record(self, db: AsyncSession, outcome: GenerationOutcome) -> None:
        run = await db.get(Run, self.claim.run_id)
        assert run is not None
        await store_scenario_set(db, run=run, behaviour=self.behaviour, generated=outcome.generated)


async def execute_generation(
    sample_id: uuid.UUID, *, models: ModelFactory = default_models
) -> None:
    settings = get_settings()

    async def plan(claim: Claim) -> GenerationWork:
        config = claim.config
        try:
            source = load_behaviours(settings.repo_root).get(config["behaviour"])
        except BehaviourError as error:
            raise SampleChanged(str(error)) from error
        if source is None or source.seed_hash != config["behaviour_seed_hash"]:
            raise SampleChanged(f"behaviour {config['behaviour']} changed after launch")
        async with session_scope() as db:
            run = await db.get(Run, claim.run_id)
            behaviour = (
                await db.get(Behaviour, run.behaviour_id) if run and run.behaviour_id else None
            )
        if behaviour is None or behaviour.seed_hash != source.seed_hash:
            raise SampleChanged("the run's behaviour version is missing")
        model = models("scenarios", config["models"]["scenarios"], config["generate"]["scenarios"])
        return GenerationWork(claim=claim, source=source, behaviour=behaviour, model=model)

    await execute(sample_id, plan)


@dataclass
class MeasureWork:
    claim: Claim
    stored: StoredAgentVersion
    behaviour: Behaviour
    definition: Behavior
    scenario_id: str
    storage: Storage
    models: ModelFactory

    async def run(self) -> SampleOutcome:
        return await run_rollout(
            run_id=str(self.claim.run_id),
            index=self.claim.index,
            epoch=self.claim.epoch,
            definition=self.definition,
            scenario_id=self.scenario_id,
            version=self.stored.adapter_input(),
            display_name=self.stored.agent.name,
            config=self.claim.config,
            storage=self.storage,
            token_limit=self.claim.token_limit,
            models=self.models,
        )

    async def record(self, db: AsyncSession, outcome: SampleOutcome) -> None:
        generated = (self.definition.scenarios or [])[self.claim.index]
        scenario = await scenario_row(
            db, self.behaviour, self.scenario_id, generated.seed, generated.variation
        )
        await index_sample(
            db,
            run_id=self.claim.run_id,
            scenario_id=scenario.id,
            sample_index=self.claim.index,
            epoch=self.claim.epoch,
            sample=outcome.sample,
            log_uri=outcome.log_uri,
            judge_model=self.claim.config["models"]["judge"],
            source=SCORE_SOURCE,
        )


async def execute_measure_sample(
    sample_id: uuid.UUID,
    *,
    models: ModelFactory = default_models,
    storage: Storage | None = None,
) -> None:
    async def plan(claim: Claim) -> MeasureWork:
        config = claim.config
        stored = await checked_agent_version(config)
        async with session_scope() as db:
            scenario_set = await db.get(ScenarioSet, uuid.UUID(config["scenario_set"]))
            behaviour = await db.get(Behaviour, scenario_set.behaviour_id) if scenario_set else None
        if scenario_set is None or behaviour is None:
            raise SampleChanged("the run's scenario set is missing")
        if scenario_set.content_hash != config["scenario_set_hash"]:
            raise SampleChanged("the scenario set changed after the run was launched")
        try:
            definition = scenario_set_definition(scenario_set)
        except MeasureError as error:
            raise SampleChanged(str(error)) from error
        scenario_id = config["seeds"][claim.index]
        ids = scenario_ids(definition)
        seeds = definition.scenarios or []
        if (
            claim.index >= len(ids)
            or ids[claim.index] != scenario_id
            or sha256_text(seeds[claim.index].seed) != config["seed_shas"][scenario_id]
        ):
            raise SampleChanged(f"scenario {scenario_id} changed after the run was launched")
        return MeasureWork(
            claim=claim,
            stored=stored,
            behaviour=behaviour,
            definition=definition,
            scenario_id=scenario_id,
            storage=storage or get_storage(),
            models=models,
        )

    await execute(sample_id, plan)
