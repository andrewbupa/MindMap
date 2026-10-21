"""Explore runs: Petri audits of an agent version, one resumable job per sample.

A run is created with its full provenance and one ``run_sample`` per seed and
epoch. Each sample is its own queue job, so a deploy that restarts the worker
loses at most the samples in flight, which are retried. When the last sample
ends, the run is closed and becomes read-only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bench_core import audit
from bench_core.agents.adapter import AdapterMode, ToolResults
from bench_core.agents.load import StoredAgentVersion
from bench_core.model_roles import ModelRoles
from bench_core.models import Run, RunKind, RunSample, RunStatus
from bench_core.provenance import Provenance
from bench_core.seeds import Seed, dimension_names, seeds_hash

ROLES = {"auditor": "auditor", "target": "target", "judge": "judge_a"}
OPEN = (RunStatus.queued.value, RunStatus.running.value)


class ExploreError(ValueError):
    pass


@dataclass(frozen=True)
class ExploreOptions:
    max_turns: int = 30
    epochs: int = 1
    token_budget: int | None = None
    tool_results: ToolResults = ToolResults.fixtures
    # Petri summarises long audits for the auditor. It counts tokens with tiktoken.
    compaction: bool = True


def engine_versions() -> dict[str, str]:
    return {package: version(package) for package in ("inspect-ai", "inspect-petri")}


def run_config(
    stored: StoredAgentVersion, seeds: list[Seed], roles: ModelRoles, options: ExploreOptions
) -> dict[str, Any]:
    return {
        "engine": "petri",
        "agent": stored.agent.key,
        "version": stored.prompt.version,
        "prompt_sha": stored.prompt.sha256,
        "tool_profile_sha": stored.tool_profile.sha256,
        "adapter": {"mode": AdapterMode.deployed.value, "tool_results": options.tool_results.value},
        "seeds": [seed.key for seed in seeds],
        "seed_shas": {seed.key: seed.sha256 for seed in seeds},
        "dimensions": {"custom": "seeds/petri/dimensions", "builtin": "petri defaults"},
        "max_turns": options.max_turns,
        "epochs": options.epochs,
        "compaction": options.compaction,
        "models": {name: roles.role(role).model for name, role in ROLES.items()},
        "generate": {name: roles.role(role).generate for name, role in ROLES.items()},
    }


async def create_run(
    db: AsyncSession,
    *,
    root: Path,
    stored: StoredAgentVersion,
    seeds: list[Seed],
    roles: ModelRoles,
    options: ExploreOptions,
    git_commit: str,
    launched_by: uuid.UUID,
) -> tuple[Run, list[RunSample]]:
    if not seeds:
        raise ExploreError("Choose at least one seed.")
    if not 1 <= options.epochs <= 10:
        raise ExploreError("Epochs must be between 1 and 10.")
    if not dimension_names(root):
        raise ExploreError("No custom judge dimensions found in seeds/petri/dimensions.")
    config = run_config(stored, seeds, roles, options)
    provenance = Provenance(
        git_commit=git_commit,
        config=config,
        model_ids=config["models"],
        prompt_sha=stored.prompt.sha256,
        seed_hash=seeds_hash(root, seeds),
        engine_versions=engine_versions(),
    )
    provenance.validate()
    run = Run(
        kind=RunKind.explore.value,
        status=RunStatus.queued.value,
        title=f"Explore: {stored.agent.name} {stored.prompt.version}, {len(seeds)} seeds",
        agent_id=stored.agent.id,
        prompt_version_id=stored.prompt.id,
        tool_profile_id=stored.tool_profile.id,
        config=config,
        config_hash=provenance.config_hash,
        git_commit=provenance.git_commit,
        prompt_sha=provenance.prompt_sha,
        seed_hash=provenance.seed_hash,
        model_ids=provenance.model_ids,
        engine_versions=provenance.engine_versions,
        adapter_mode=AdapterMode.deployed.value,
        token_budget=options.token_budget or roles.budget("explore"),
        launched_by=launched_by,
    )
    db.add(run)
    await db.flush()
    samples = [
        RunSample(run_id=run.id, sample_index=index, epoch=epoch)
        for epoch in range(1, options.epochs + 1)
        for index in range(len(seeds))
    ]
    db.add_all(samples)
    await db.flush()
    await audit.record(
        db,
        "run.launch",
        actor_id=launched_by,
        target_type="run",
        target_id=run.id,
        detail={"kind": run.kind, "samples": len(samples), "config_hash": run.config_hash},
    )
    return run, samples


async def sample_counts(db: AsyncSession, run_id: uuid.UUID) -> dict[str, int]:
    rows = await db.execute(
        select(RunSample.status, func.count())
        .where(RunSample.run_id == run_id)
        .group_by(RunSample.status)
    )
    return {status: count for status, count in rows.all()}


async def maybe_finish(db: AsyncSession, run_id: uuid.UUID) -> Run | None:
    """Close the run if no sample is still queued or running. Safe to call concurrently."""
    run = (
        await db.execute(select(Run).where(Run.id == run_id).with_for_update())
    ).scalar_one_or_none()
    if run is None or run.status not in OPEN:
        return None
    counts = await sample_counts(db, run_id)
    if any(counts.get(status, 0) for status in OPEN):
        return None
    total = sum(counts.values())
    failed = counts.get(RunStatus.failed.value, 0)
    stopped = counts.get(RunStatus.stopped_at_budget.value, 0)
    if stopped:
        run.status = RunStatus.stopped_at_budget.value
    elif failed == total:
        run.status = RunStatus.failed.value
    else:
        run.status = RunStatus.succeeded.value
    if failed:
        run.error = f"{failed} of {total} samples failed."
    run.finished_at = datetime.now(UTC)
    await audit.record(
        db,
        "run.finish",
        actor_id=None,
        target_type="run",
        target_id=run.id,
        detail={"status": run.status, "samples": counts, "tokens_used": run.tokens_used},
    )
    return run
