"""Run one Tally rollout: one Bloom scenario against our agent, judged for presence.

This follows petri_bloom's own task, ``bloom_audit``, and keeps its dataset, judge
instructions, viewer and metadata. Only the solver changes: Bloom's auditor with the
same tools and system message, aimed at Agora's Petri target instead of a bare model,
so the agent's real system prompt stays fixed. One sample runs per job.
"""

from __future__ import annotations

from typing import Any

from inspect_ai import Task, task_with
from inspect_petri import audit_solver, auditor_agent, auditor_tools
from petri_bloom import Behavior, bloom_audit
from petri_bloom._evaluation.prompts import format_system_message

from agora_core.agents.adapter import AgentVersion
from agora_core.storage import Storage
from agora_worker.inquiry.runner import (
    ModelFactory,
    SampleOutcome,
    default_models,
    role_models,
    run_task,
)
from agora_worker.inquiry.target import agora_target


def rollout_task(
    definition: Behavior,
    scenario_id: str,
    *,
    version: AgentVersion,
    display_name: str,
    config: dict[str, Any],
) -> Task:
    base = bloom_audit(definition, max_turns=config["max_turns"], compaction=config["compaction"])
    dataset = base.dataset.filter(lambda sample: sample.id == scenario_id)
    if len(dataset) != 1:
        raise RuntimeError(f"scenario {scenario_id} is not in the scenario set")
    auditor = auditor_agent(
        max_turns=config["max_turns"],
        compaction=config["compaction"],
        # Our target answers its own tools from fixtures, so the auditor gets none.
        tools=auditor_tools(prefill=False, rollback=False, target_tools="none"),
        system_message=format_system_message(definition),
        turn_counter=True,
        target_display_name=display_name,
    )
    return task_with(
        base, dataset=dataset, solver=audit_solver(auditor=auditor, target=agora_target(version))
    )


async def run_rollout(
    *,
    run_id: str,
    index: int,
    epoch: int,
    definition: Behavior,
    scenario_id: str,
    version: AgentVersion,
    display_name: str,
    config: dict[str, Any],
    storage: Storage,
    token_limit: int | None,
    models: ModelFactory = default_models,
) -> SampleOutcome:
    task = rollout_task(
        definition, scenario_id, version=version, display_name=display_name, config=config
    )
    return await run_task(
        task,
        run_id=run_id,
        index=index,
        epoch=epoch,
        storage=storage,
        token_limit=token_limit,
        roles=role_models(config, models),
        metadata={"behaviour": config["behaviour"], "scenario": scenario_id},
    )
