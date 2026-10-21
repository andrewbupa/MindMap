from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from bench_api.deps import Db, ReaderUser
from bench_api.schemas import RunOut, SignedUrlOut
from bench_core import audit
from bench_core.models import Run
from bench_core.storage import get_storage
from bench_core.transcripts import key_from_uri

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}")
async def read_run(run_id: uuid.UUID, _: ReaderUser, db: Db) -> RunOut:
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such run.")
    return RunOut.model_validate(run)


@router.get("/{run_id}/log")
async def run_log(run_id: uuid.UUID, user: ReaderUser, db: Db) -> SignedUrlOut:
    """A short-lived link to the run's Inspect log."""
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such run.")
    if not run.log_uri:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This run has not written its log yet.")
    storage = get_storage()
    key = key_from_uri(run.log_uri)
    await audit.record(
        db,
        "storage.signed_url",
        actor_id=user.id,
        target_type="run",
        target_id=run.id,
        detail={"key": key},
    )
    await db.commit()
    return SignedUrlOut(
        url=storage.signed_url(key, filename=f"{run.id}.eval"),
        expires_in=storage.signed_url_seconds,
    )
