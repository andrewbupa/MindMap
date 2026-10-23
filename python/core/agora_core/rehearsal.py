"""Rehearsal conversations: a person chats with an agent version, and the result is a run.

A rehearsal run records the same provenance as any other run. Each turn goes
through the adapter; when the person finishes, or the token budget is reached,
the conversation is written to Spaces as an Inspect transcript and the run becomes
read-only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from inspect_ai.model import ChatMessageUser, ModelUsage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core import audit
from agora_core.agents.adapter import AgentAdapter
from agora_core.agents.load import StoredAgentVersion
from agora_core.model_roles import ModelRoles
from agora_core.models import Message, Run, RunKind, RunStatus, Transcript
from agora_core.provenance import Provenance
from agora_core.storage import Storage
from agora_core.transcripts import (
    append_messages,
    build_log,
    load_messages,
    log_key,
    store_log,
)

TASK = "agora/rehearsal"


class RehearsalError(RuntimeError):
    pass


@dataclass(frozen=True)
class TurnResult:
    messages: list[Message]
    stopped_at_budget: bool


def _usage(transcript: Transcript) -> dict[str, int]:
    usage = transcript.meta.get("usage") or {}
    return {key: int(usage.get(key, 0)) for key in ("input", "output", "reasoning")}


async def start(
    db: AsyncSession,
    *,
    stored: StoredAgentVersion,
    adapter: AgentAdapter,
    roles: ModelRoles,
    git_commit: str,
    launched_by: uuid.UUID,
    persona_key: str | None,
    context: str | None,
    caller_system: str | None,
) -> Run:
    config: dict[str, Any] = {
        **adapter.config,
        "persona": persona_key,
        "context": context or None,
        "caller_system": caller_system or None,
    }
    provenance = Provenance(
        git_commit=git_commit,
        config=config,
        model_ids={"target": adapter.model_id},
        prompt_sha=stored.prompt.sha256,
        engine_versions={"tool_profile": stored.tool_profile.sha256},
    )
    provenance.validate()
    now = datetime.now(UTC)
    run = Run(
        kind=RunKind.rehearsal.value,
        status=RunStatus.running.value,
        title=f"Rehearsal: {stored.agent.name} {stored.prompt.version}",
        agent_id=stored.agent.id,
        prompt_version_id=stored.prompt.id,
        tool_profile_id=stored.tool_profile.id,
        config=config,
        config_hash=provenance.config_hash,
        git_commit=provenance.git_commit,
        prompt_sha=provenance.prompt_sha,
        model_ids=provenance.model_ids,
        engine_versions=provenance.engine_versions,
        adapter_mode=adapter.mode.value,
        token_budget=roles.budget("rehearsal"),
        launched_by=launched_by,
        started_at=now,
    )
    db.add(run)
    await db.flush()
    transcript = Transcript(
        run_id=run.id,
        sample_index=0,
        meta={"usage": {"input": 0, "output": 0, "reasoning": 0}},
    )
    db.add(transcript)
    await db.flush()
    system = adapter.system_message(context=context, caller_system=caller_system)
    if system is not None:
        await append_messages(db, transcript, [system])
    await audit.record(
        db,
        "run.launch",
        actor_id=launched_by,
        target_type="run",
        target_id=run.id,
        detail={"kind": run.kind, "config_hash": run.config_hash},
    )
    return run


async def transcript_for(db: AsyncSession, run: Run) -> Transcript:
    return (await db.execute(select(Transcript).where(Transcript.run_id == run.id))).scalar_one()


async def take_turn(
    db: AsyncSession, run: Run, adapter: AgentAdapter, roles: ModelRoles, content: str
) -> TurnResult:
    if run.status != RunStatus.running.value:
        raise RehearsalError("This conversation has finished. Start a new one to continue.")
    if run.tokens_used >= run.token_budget:
        raise RehearsalError("This conversation has used its token budget.")
    transcript = await transcript_for(db, run)
    history = await load_messages(db, transcript.id)
    user = ChatMessageUser(content=content)
    turn = await adapter.respond([*history, user])
    rows = await append_messages(db, transcript, [user, *turn.messages])

    usage = _usage(transcript)
    usage["input"] += turn.usage.input_tokens
    usage["output"] += turn.usage.output_tokens
    usage["reasoning"] += turn.usage.reasoning_tokens
    transcript.meta = {**transcript.meta, "usage": usage}
    run.tokens_used += turn.usage.total
    run.cost_usd = Decimal(run.cost_usd) + roles.cost_usd(
        adapter.model_id, turn.usage.input_tokens, turn.usage.output_tokens
    )
    return TurnResult(rows, stopped_at_budget=run.tokens_used >= run.token_budget)


async def finish(
    db: AsyncSession,
    run: Run,
    storage: Storage,
    *,
    actor_id: uuid.UUID | None,
    status: RunStatus = RunStatus.succeeded,
) -> Run:
    """Write the transcript to Spaces, then mark the run finished. After this it is read-only."""
    if run.status != RunStatus.running.value:
        raise RehearsalError("This conversation has already finished.")
    transcript = await transcript_for(db, run)
    messages = await load_messages(db, transcript.id)
    usage = _usage(transcript)
    model_id = run.model_ids["target"]
    log = build_log(
        run=run,
        transcript=transcript,
        messages=messages,
        model_id=model_id,
        generate=run.config.get("generate", {}),
        usage=ModelUsage(
            input_tokens=usage["input"],
            output_tokens=usage["output"],
            total_tokens=usage["input"] + usage["output"],
            reasoning_tokens=usage["reasoning"] or None,
        ),
        task=TASK,
        metadata={
            "agora_run_id": str(run.id),
            "agent": run.config.get("agent"),
            "version": run.config.get("version"),
            "prompt_sha": run.prompt_sha,
            "tool_profile_sha": run.config.get("tool_profile_sha"),
            "config_hash": run.config_hash,
            "git_commit": run.git_commit,
            "adapter_mode": run.adapter_mode,
            "persona": run.config.get("persona"),
            "thinking": "Assistant reasoning blocks are summaries written by a separate model.",
        },
    )
    key = log_key(run.id, transcript.id)
    uri = await store_log(storage, log, key)
    transcript.log_uri = uri
    await db.flush()
    run.log_uri = uri
    run.status = status.value
    run.finished_at = datetime.now(UTC)
    await audit.record(
        db,
        "run.finish",
        actor_id=actor_id,
        target_type="run",
        target_id=run.id,
        detail={"status": run.status, "log_uri": uri, "tokens_used": run.tokens_used},
    )
    await db.flush()
    return run
