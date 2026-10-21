"""Reports: exports of a run with its full provenance. Every export is audited."""

from __future__ import annotations

import csv
import io
import json
import uuid

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select

from bench_api.deps import Db, ReaderUser
from bench_core import audit
from bench_core.models import Run, Scenario, Score, Transcript

router = APIRouter(prefix="/reports", tags=["reports"])

PROVENANCE = (
    "run_id",
    "run_kind",
    "run_status",
    "git_commit",
    "config_hash",
    "prompt_sha",
    "seed_hash",
    "taxonomy_version",
    "model_ids",
    "engine_versions",
)


def provenance(run: Run) -> dict[str, str]:
    return {
        "run_id": str(run.id),
        "run_kind": run.kind,
        "run_status": run.status,
        "git_commit": run.git_commit,
        "config_hash": run.config_hash,
        "prompt_sha": run.prompt_sha or "",
        "seed_hash": run.seed_hash or "",
        "taxonomy_version": run.taxonomy_version or "",
        "model_ids": json.dumps(run.model_ids, sort_keys=True),
        "engine_versions": json.dumps(run.engine_versions, sort_keys=True),
    }


@router.get("/runs/{run_id}/scores.csv", response_class=Response)
async def export_scores(run_id: uuid.UUID, user: ReaderUser, db: Db) -> Response:
    """One row per transcript and dimension, each carrying the run's provenance.
    Scores from transcripts with content notes are included; their text is not."""
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such run.")
    rows = (
        await db.execute(
            select(Transcript, Score, Scenario)
            .join(Score, Score.transcript_id == Transcript.id)
            .outerjoin(Scenario, Scenario.id == Transcript.scenario_id)
            .where(Transcript.run_id == run.id)
            .order_by(Transcript.sample_index, Transcript.epoch, Score.dimension)
        )
    ).all()
    buffer = io.StringIO()
    fields = [
        "transcript_id",
        "scenario",
        "epoch",
        "dimension",
        "value",
        "scale_max",
        "judge_model",
        "log_uri",
        *PROVENANCE,
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    shared = provenance(run)
    for transcript, score, scenario in rows:
        writer.writerow(
            {
                "transcript_id": str(transcript.id),
                "scenario": scenario.key if scenario else "",
                "epoch": transcript.epoch,
                "dimension": score.dimension,
                "value": score.value,
                "scale_max": score.scale_max,
                "judge_model": score.judge_model or "",
                "log_uri": transcript.log_uri or "",
                **shared,
            }
        )
    await audit.record(
        db,
        "report.export",
        actor_id=user.id,
        target_type="run",
        target_id=run.id,
        detail={"format": "csv", "rows": len(rows)},
    )
    await db.commit()
    return Response(
        buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="bench-{run.kind}-{run.id}.csv"'},
    )


@router.get("/runs/{run_id}/provenance")
async def run_provenance(run_id: uuid.UUID, user: ReaderUser, db: Db) -> dict[str, object]:
    """Everything needed to reproduce the run, including its full config."""
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such run.")
    await audit.record(
        db, "report.provenance", actor_id=user.id, target_type="run", target_id=run.id
    )
    await db.commit()
    return {**provenance(run), "config": run.config, "title": run.title}
