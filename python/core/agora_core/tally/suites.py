"""Scenario generation runs and Tally suites.

Generation is a run of kind ``scenarios`` with one sample: petri_bloom's
understanding and ideation for one behaviour version. Its output, a scenario set,
is written once and reused, so every prompt version measured against it faces
identical scenarios.

A suite is one Tally run per prompt version, all against the same scenario set,
with one sample per scenario and repetition. Each rollout runs our agent through
the same Petri target as Inquiry, which keeps the agent's real system prompt and
passes the auditor's staged context as a delimited block. Runs record this route.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from importlib.metadata import version
from typing import Any

from petri_bloom import Behavior
from petri_bloom._behavior.behavior import unique_scenario_id
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core import audit
from agora_core.agents.adapter import AdapterMode, ToolResults
from agora_core.agents.load import StoredAgentVersion
from agora_core.model_roles import ModelRoles
from agora_core.models import Behaviour, Run, RunKind, RunSample, RunStatus, Scenario, ScenarioSet
from agora_core.provenance import Provenance, canonical_json, sha256_text
from agora_core.tally.behaviours import BehaviourSource, behaviour_row
from agora_core.tally.rates import THRESHOLD

GENERATION_ROLES = {"scenarios": "scenarios"}
ROLLOUT_ROLES = {"auditor": "auditor", "target": "target", "judge": "judge_a"}
# Our Petri target holds the agent's prompt fixed; the alternative in the brief is the
# OpenAI-compatible endpoint. Every Tally run records which one it used.
ROUTE = "petri_target"
PRESENCE_TAG = "behavior"
SCORE_SOURCE = "bloom_judge"


class TallyError(ValueError):
    pass


@dataclass(frozen=True)
class TallyOptions:
    epochs: int = 3
    max_turns: int = 15
    token_budget: int | None = None
    tool_results: ToolResults = ToolResults.fixtures
    # Petri summarises long audits for the auditor. It counts tokens with tiktoken.
    compaction: bool = True


def engine_versions() -> dict[str, str]:
    return {package: version(package) for package in ("inspect-ai", "inspect-petri", "petri-bloom")}


def content_hash(content: dict[str, Any]) -> str:
    return sha256_text(canonical_json(content))


def presence_dimension(definition: Behavior) -> str:
    """The generated dimension that scores the behaviour. petri_bloom tags it "behavior"."""
    tagged = [d.name for d in definition.dimensions or [] if PRESENCE_TAG in d.tags]
    if len(tagged) != 1:
        raise TallyError(
            f"expected one dimension tagged {PRESENCE_TAG!r}, found {len(tagged)}: {tagged}"
        )
    return tagged[0]


def scenario_ids(definition: Behavior) -> list[str]:
    """Sample ids in dataset order, computed exactly as petri_bloom's dataset does."""
    used: set[str] = set()
    return [unique_scenario_id(scenario, used) for scenario in definition.scenarios or []]


def scenario_key(behaviour_key: str, scenario_id: str) -> str:
    return f"{behaviour_key}/{scenario_id}"


def scenario_set_definition(scenario_set: ScenarioSet) -> Behavior:
    """The stored scenario set as petri_bloom's Behavior, refusing one that was altered."""
    if content_hash(scenario_set.content) != scenario_set.content_hash:
        raise TallyError(f"scenario set {scenario_set.id} does not match its hash")
    return Behavior.model_validate(scenario_set.content)


def suite_seed_hash(behaviour: Behaviour, scenario_set: ScenarioSet) -> str:
    """What a rate is cited with: the behaviour's seed hash and its scenario set's hash."""
    return sha256_text(
        canonical_json({"behaviour": behaviour.seed_hash, "scenarios": scenario_set.content_hash})
    )


async def create_generation_run(
    db: AsyncSession,
    *,
    source: BehaviourSource,
    roles: ModelRoles,
    git_commit: str,
    launched_by: uuid.UUID,
    token_budget: int | None = None,
) -> tuple[Run, RunSample]:
    behaviour = await behaviour_row(db, source, git_commit)
    config: dict[str, Any] = {
        "engine": "bloom",
        "stage": "scenarios",
        "behaviour": source.key,
        "behaviour_seed_hash": source.seed_hash,
        "num_scenarios": source.definition.num_scenarios,
        "variations": sorted(source.definition.variations),
        "models": {name: roles.role(role).model for name, role in GENERATION_ROLES.items()},
        "generate": {
            name: roles.role(role).call_generate for name, role in GENERATION_ROLES.items()
        },
    }
    provenance = Provenance(
        git_commit=git_commit,
        config=config,
        model_ids=config["models"],
        seed_hash=source.seed_hash,
        engine_versions=engine_versions(),
    )
    provenance.validate()
    run = Run(
        kind=RunKind.scenarios.value,
        status=RunStatus.queued.value,
        title=f"Scenarios: {source.title}",
        behaviour_id=behaviour.id,
        config=config,
        config_hash=provenance.config_hash,
        git_commit=provenance.git_commit,
        seed_hash=provenance.seed_hash,
        model_ids=provenance.model_ids,
        engine_versions=provenance.engine_versions,
        token_budget=token_budget or roles.budget("scenarios", roles.budget("tally")),
        launched_by=launched_by,
    )
    db.add(run)
    await db.flush()
    sample = RunSample(run_id=run.id, sample_index=0, epoch=1)
    db.add(sample)
    await db.flush()
    await audit.record(
        db,
        "run.launch",
        actor_id=launched_by,
        target_type="run",
        target_id=run.id,
        detail={"kind": run.kind, "behaviour": source.key, "config_hash": run.config_hash},
    )
    return run, sample


DOMAINS = {"claims", "coverage", "disputes", "health_support"}


async def store_scenario_set(
    db: AsyncSession, *, run: Run, behaviour: Behaviour, generated: Behavior
) -> ScenarioSet:
    """Write a generation run's output: the scenario set, and a scenario row per seed."""
    dimension = presence_dimension(generated)
    ids = scenario_ids(generated)
    if not ids:
        raise TallyError("Bloom generated no scenarios")
    content = generated.model_dump(mode="json")
    scenario_set = ScenarioSet(
        run_id=run.id,
        behaviour_id=behaviour.id,
        content=content,
        content_hash=content_hash(content),
        presence_dimension=dimension,
        scenario_count=len(ids),
    )
    db.add(scenario_set)
    for scenario_id, scenario in zip(ids, generated.scenarios or [], strict=True):
        await scenario_row(db, behaviour, scenario_id, scenario.seed, scenario.variation)
    await db.flush()
    return scenario_set


async def scenario_row(
    db: AsyncSession, behaviour: Behaviour, scenario_id: str, seed: str, variation: str | None
) -> Scenario:
    """The scenario row for one generated seed, created on first use.

    It carries the behaviour's scenario type, for Ethos, and its content notes, which
    gate who may read the transcripts."""
    key = scenario_key(behaviour.key, scenario_id)
    digest = sha256_text(seed)
    found = (
        await db.execute(select(Scenario).where(Scenario.key == key, Scenario.sha256 == digest))
    ).scalar_one_or_none()
    if found is not None:
        return found
    metadata = behaviour.seed_config.get("metadata") or {}
    tags = [str(tag) for tag in behaviour.seed_config.get("tags") or []]
    row = Scenario(
        key=key,
        title=scenario_id.replace("_", " ").capitalize(),
        situation=seed,
        scenario_type=metadata.get("scenario_type"),
        domain_tags=[tag for tag in tags if tag in DOMAINS],
        risk_tags=[tag for tag in tags if tag not in DOMAINS]
        + ([f"variation:{variation}"] if variation else []),
        content_notes=[str(note) for note in metadata.get("content_notes") or []],
        seed_text=seed,
        source="bloom",
        sha256=digest,
    )
    db.add(row)
    await db.flush()
    return row


def tally_config(
    *,
    stored: StoredAgentVersion,
    behaviour: Behaviour,
    scenario_set: ScenarioSet,
    definition: Behavior,
    roles: ModelRoles,
    options: TallyOptions,
    suite_id: uuid.UUID,
) -> dict[str, Any]:
    ids = scenario_ids(definition)
    return {
        "engine": "bloom",
        "stage": "rollout",
        "route": ROUTE,
        "suite": str(suite_id),
        "agent": stored.agent.key,
        "version": stored.prompt.version,
        "prompt_sha": stored.prompt.sha256,
        "tool_profile_sha": stored.tool_profile.sha256,
        "adapter": {"mode": AdapterMode.deployed.value, "tool_results": options.tool_results.value},
        "behaviour": behaviour.key,
        "behaviour_seed_hash": behaviour.seed_hash,
        "scenario_set": str(scenario_set.id),
        "scenario_set_hash": scenario_set.content_hash,
        "presence_dimension": scenario_set.presence_dimension,
        "threshold": THRESHOLD,
        "seeds": ids,
        "seed_shas": {
            scenario_id: sha256_text(scenario.seed)
            for scenario_id, scenario in zip(ids, definition.scenarios or [], strict=True)
        },
        "max_turns": options.max_turns,
        "epochs": options.epochs,
        "compaction": options.compaction,
        "models": {name: roles.role(role).model for name, role in ROLLOUT_ROLES.items()},
        "generate": {name: roles.role(role).call_generate for name, role in ROLLOUT_ROLES.items()},
        "thinking": {"target": roles.role("target").thinking},
    }


async def create_tally_run(
    db: AsyncSession,
    *,
    stored: StoredAgentVersion,
    scenario_set: ScenarioSet,
    roles: ModelRoles,
    options: TallyOptions,
    git_commit: str,
    launched_by: uuid.UUID,
    suite_id: uuid.UUID,
) -> tuple[Run, list[RunSample]]:
    if not 1 <= options.epochs <= 10:
        raise TallyError("Repetitions must be between 1 and 10.")
    behaviour = await db.get(Behaviour, scenario_set.behaviour_id)
    if behaviour is None:
        raise TallyError("The scenario set's behaviour is missing.")
    agents = behaviour.seed_config.get("metadata", {}).get("agents") or []
    if agents and stored.agent.key not in agents:
        raise TallyError(
            f"{behaviour.name} is measured on {', '.join(agents)}, not {stored.agent.key}."
        )
    definition = scenario_set_definition(scenario_set)
    config = tally_config(
        stored=stored,
        behaviour=behaviour,
        scenario_set=scenario_set,
        definition=definition,
        roles=roles,
        options=options,
        suite_id=suite_id,
    )
    provenance = Provenance(
        git_commit=git_commit,
        config=config,
        model_ids=config["models"],
        prompt_sha=stored.prompt.sha256,
        seed_hash=suite_seed_hash(behaviour, scenario_set),
        engine_versions=engine_versions(),
    )
    provenance.validate()
    run = Run(
        kind=RunKind.tally.value,
        status=RunStatus.queued.value,
        title=f"Tally: {behaviour.name}, {stored.agent.name} {stored.prompt.version}",
        agent_id=stored.agent.id,
        prompt_version_id=stored.prompt.id,
        tool_profile_id=stored.tool_profile.id,
        behaviour_id=behaviour.id,
        config=config,
        config_hash=provenance.config_hash,
        git_commit=provenance.git_commit,
        prompt_sha=provenance.prompt_sha,
        seed_hash=provenance.seed_hash,
        model_ids=provenance.model_ids,
        engine_versions=provenance.engine_versions,
        adapter_mode=AdapterMode.deployed.value,
        route=ROUTE,
        token_budget=options.token_budget or roles.budget("tally"),
        launched_by=launched_by,
    )
    db.add(run)
    await db.flush()
    samples = [
        RunSample(run_id=run.id, sample_index=index, epoch=epoch)
        for epoch in range(1, options.epochs + 1)
        for index in range(len(config["seeds"]))
    ]
    db.add_all(samples)
    await db.flush()
    await audit.record(
        db,
        "run.launch",
        actor_id=launched_by,
        target_type="run",
        target_id=run.id,
        detail={
            "kind": run.kind,
            "samples": len(samples),
            "config_hash": run.config_hash,
            "suite": str(suite_id),
        },
    )
    return run, samples


async def latest_scenario_set(db: AsyncSession, behaviour_key: str) -> ScenarioSet | None:
    return (
        await db.execute(
            select(ScenarioSet)
            .join(Behaviour, Behaviour.id == ScenarioSet.behaviour_id)
            .where(Behaviour.key == behaviour_key)
            .order_by(ScenarioSet.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
