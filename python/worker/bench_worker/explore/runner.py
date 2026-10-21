"""Run one Explore sample: a Petri audit of one seed against our agent.

The audit runs through Inspect's Python API into a temporary log directory. The
``.eval`` log is uploaded to Spaces, and the target's conversation and the judge's
scores are indexed in Postgres. Petri keeps a sample's state in memory, so an
interrupted sample is re-run from the start; one sample per job keeps that cheap.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from inspect_ai import eval_async
from inspect_ai.log import EvalLog, EvalSample, read_eval_log_async
from inspect_ai.model import GenerateConfig, Model, get_model
from inspect_petri import JudgeDimension, audit, judge_dimensions

from bench_core.agents.adapter import AgentVersion
from bench_core.seeds import Seed, dimensions_dir
from bench_core.storage import Storage, object_key
from bench_worker.explore.target import bench_target

os.environ.setdefault("INSPECT_DISPLAY", "none")

JUDGE_SCORER = "audit_judge"

# Inspect refuses concurrent eval_async calls in one process, so audits in a worker
# run one at a time and the queue waits. Add worker instances to run more at once.
EVAL_LOCK = asyncio.Lock()

# Builds the model for a role ("auditor", "target" or "judge") from its recorded ID and settings.
ModelFactory = Callable[[str, str, dict[str, Any]], Model]


def default_models(role: str, model_id: str, generate: dict[str, Any]) -> Model:
    return get_model(model_id, config=GenerateConfig(**generate))


def dimensions(root: Path) -> list[str | JudgeDimension]:
    """Petri's built-in dimensions, then ours. A directory alone would replace the defaults."""
    builtin: list[str | JudgeDimension] = [dimension.name for dimension in judge_dimensions()]
    return [*builtin, *judge_dimensions(dimensions_dir(root))]


@dataclass
class SampleOutcome:
    log: EvalLog
    sample: EvalSample
    log_uri: str
    usage: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def limit_reached(self) -> bool:
        return self.sample.limit is not None

    @property
    def tokens(self) -> int:
        return sum(u["input"] + u["output"] for u in self.usage.values())


def sample_key(run_id: str, index: int, epoch: int) -> str:
    return object_key("runs", run_id, "samples", f"{index:04d}-e{epoch}.eval")


async def run_audit(
    *,
    run_id: str,
    index: int,
    epoch: int,
    seed: Seed,
    version: AgentVersion,
    display_name: str,
    config: dict[str, Any],
    root: Path,
    storage: Storage,
    token_limit: int | None,
    models: ModelFactory = default_models,
) -> SampleOutcome:
    with tempfile.TemporaryDirectory(prefix="bench-explore-") as scratch:
        seed_dir = Path(scratch) / "seeds"
        seed_dir.mkdir()
        shutil.copyfile(seed.path, seed_dir / f"{seed.key}.md")
        task = audit(
            seed_instructions=str(seed_dir),
            target=bench_target(version),
            target_tools="none",
            judge_dimensions=dimensions(root),
            max_turns=config["max_turns"],
            compaction=config.get("compaction", True),
            target_display_name=display_name,
        )
        roles = {
            role: models(role, config["models"][role], config["generate"].get(role, {}))
            for role in ("auditor", "target", "judge")
        }
        async with EVAL_LOCK:
            logs = await eval_async(
                task,
                model_roles=roles,
                log_dir=str(Path(scratch) / "logs"),
                log_format="eval",
                token_limit=token_limit,
                fail_on_error=False,
                tags=["bench", f"run:{run_id}"],
                metadata={"bench_run_id": run_id, "seed": seed.key, "epoch": epoch},
            )
        location = logs[0].location
        log = await read_eval_log_async(location)
        uri = f"s3://{storage.bucket}/{sample_key(run_id, index, epoch)}"
        await storage.aput_file(sample_key(run_id, index, epoch), Path(location), "application/zip")

    if not log.samples:
        raise RuntimeError(f"the audit produced no sample: {log.error or log.status}")
    sample = log.samples[0]
    if sample.error is not None:
        raise RuntimeError(f"the audit failed: {sample.error.message}")
    usage = {
        model: {"input": u.input_tokens, "output": u.output_tokens}
        for model, u in (log.stats.model_usage or {}).items()
    }
    return SampleOutcome(log=log, sample=sample, log_uri=uri, usage=usage)
