"""Index a finished Petri sample: the target's conversation and the judge's scores."""

from __future__ import annotations

import math
import uuid
from typing import Any

from inspect_ai.log import EvalSample
from sqlalchemy.ext.asyncio import AsyncSession

from bench_core.models import Score, Transcript
from bench_core.transcripts import append_messages
from bench_worker.explore.runner import JUDGE_SCORER

SCALE_MAX = 10.0


def judge_references(sample: EvalSample, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    """The judge cites messages as [M3]; resolve each cite to a message in the indexed
    conversation. Cites into abandoned rollback branches keep their id but no index."""
    index_by_id = {message.id: index for index, message in enumerate(sample.messages)}
    return [
        {
            "cite": reference.get("cite"),
            "message_id": reference.get("id"),
            "message_index": index_by_id.get(reference.get("id")),
        }
        for reference in metadata.get("scanner_references") or []
        if reference.get("type") == "message"
    ]


async def index_sample(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    scenario_id: uuid.UUID,
    sample_index: int,
    epoch: int,
    sample: EvalSample,
    log_uri: str,
    judge_model: str,
) -> Transcript:
    score = (sample.scores or {}).get(JUDGE_SCORER)
    metadata: dict[str, Any] = dict(score.metadata or {}) if score else {}
    references = judge_references(sample, metadata)
    transcript = Transcript(
        run_id=run_id,
        scenario_id=scenario_id,
        sample_index=sample_index,
        epoch=epoch,
        inspect_sample_id=str(sample.id),
        log_uri=log_uri,
        summary=metadata.get("summary"),
        meta={
            "highlights": metadata.get("highlights"),
            "judge_references": references,
            "judge_refused": bool(metadata.get("refusal")),
            "limit": sample.limit.type if sample.limit else None,
        },
    )
    db.add(transcript)
    await db.flush()
    await append_messages(db, transcript, list(sample.messages))

    values = score.value if score and isinstance(score.value, dict) else {}
    for dimension, value in sorted(values.items()):
        if not isinstance(value, int | float) or math.isnan(value):
            continue
        db.add(
            Score(
                transcript_id=transcript.id,
                source="petri_judge",
                dimension=dimension,
                value=float(value),
                scale_max=SCALE_MAX,
                explanation=score.explanation if score else None,
                highlights=references,
                judge_model=judge_model,
            )
        )
    await db.flush()
    return transcript
