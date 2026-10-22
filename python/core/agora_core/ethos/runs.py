"""Ethos runs: a judge panel reads the transcripts of a finished run.

An Ethos run records its source run, the taxonomy version, the panel's exact models
and the transcripts it read. Each transcript is one sample job, in which every judge
reads every family. The run carries its source's prompt SHA and seed hash, so an Ethos
finding can be traced to the prompt and scenarios behind the conversation.
"""

from __future__ import annotations

import uuid
from importlib.metadata import version
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core import audit
from agora_core.ethos.panel import check_panel
from agora_core.ethos.taxonomy import load_ethos, sync_ethos
from agora_core.model_roles import ModelRoles
from agora_core.models import (
    FINISHED_STATUSES,
    Run,
    RunKind,
    RunSample,
    RunStatus,
    Transcript,
)
from agora_core.provenance import Provenance

PANEL = "ethos"
READABLE = {RunKind.inquiry.value, RunKind.tally.value, RunKind.rehearsal.value}


class EthosError(ValueError):
    pass


def engine_versions() -> dict[str, str]:
    return {package: version(package) for package in ("inspect-ai", "inspect-scout")}


async def create_ethos_run(
    db: AsyncSession,
    *,
    root: Path,
    source: Run,
    roles: ModelRoles,
    git_commit: str,
    launched_by: uuid.UUID,
    transcript_ids: list[uuid.UUID] | None = None,
    token_budget: int | None = None,
) -> tuple[Run, list[RunSample]]:
    if source.kind not in READABLE:
        raise EthosError("Ethos reads Inquiry, Tally and rehearsal runs.")
    if source.status not in {status.value for status in FINISHED_STATUSES}:
        raise EthosError("Ethos reads finished runs only; this one is still going.")
    query = (
        select(Transcript)
        .where(Transcript.run_id == source.id)
        .order_by(Transcript.sample_index, Transcript.epoch)
    )
    transcripts = list((await db.execute(query)).scalars())
    if transcript_ids is not None:
        wanted = set(transcript_ids)
        transcripts = [t for t in transcripts if t.id in wanted]
        if len(transcripts) != len(wanted):
            raise EthosError("Some of those transcripts are not in the source run.")
    if not transcripts:
        raise EthosError("The source run has no transcripts to read.")

    panel = roles.panel(PANEL)
    check_panel(list(panel.values()))
    spec = load_ethos(root)
    taxonomy = await sync_ethos(db, spec, git_commit)
    families = list(spec.taxonomy.families)
    config: dict[str, Any] = {
        "engine": "ethos",
        "source_run": str(source.id),
        "source_kind": source.kind,
        "agent": source.config.get("agent"),
        "version": source.config.get("version"),
        "taxonomy_version": taxonomy.version,
        "taxonomy_sha": taxonomy.sha256,
        "families": families,
        "panel": panel,
        "generate": {role: roles.role(role).call_generate for role in panel},
        "transcripts": [str(t.id) for t in transcripts],
    }
    provenance = Provenance(
        git_commit=git_commit,
        config=config,
        model_ids=panel,
        prompt_sha=source.prompt_sha,
        seed_hash=source.seed_hash,
        taxonomy_version=taxonomy.version,
        engine_versions=engine_versions(),
    )
    provenance.validate()
    run = Run(
        kind=RunKind.ethos.value,
        status=RunStatus.queued.value,
        title=f"Ethos: {source.title}",
        agent_id=source.agent_id,
        prompt_version_id=source.prompt_version_id,
        tool_profile_id=source.tool_profile_id,
        behaviour_id=source.behaviour_id,
        source_run_id=source.id,
        config=config,
        config_hash=provenance.config_hash,
        git_commit=provenance.git_commit,
        prompt_sha=provenance.prompt_sha,
        seed_hash=provenance.seed_hash,
        taxonomy_version=provenance.taxonomy_version,
        model_ids=provenance.model_ids,
        engine_versions=provenance.engine_versions,
        adapter_mode=source.adapter_mode,
        token_budget=token_budget or roles.budget("ethos"),
        launched_by=launched_by,
    )
    db.add(run)
    await db.flush()
    samples = [RunSample(run_id=run.id, sample_index=i, epoch=1) for i in range(len(transcripts))]
    db.add_all(samples)
    await db.flush()
    await audit.record(
        db,
        "run.launch",
        actor_id=launched_by,
        target_type="run",
        target_id=run.id,
        detail={"kind": run.kind, "source_run": str(source.id), "samples": len(samples)},
    )
    return run, samples
