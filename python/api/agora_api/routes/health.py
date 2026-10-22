from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from agora_api.deps import AppSettings, Db
from agora_api.schemas import HealthOut, ReadinessOut
from agora_core.provenance import current_git_commit

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health(settings: AppSettings) -> HealthOut:
    """Liveness: the process is up. Never touches the database."""
    return HealthOut(
        status="ok",
        environment=settings.environment.value,
        commit=current_git_commit(settings.repo_root, settings.git_commit),
    )


@router.get("/ready")
async def ready(db: Db, response: Response) -> ReadinessOut:
    """Readiness: the database answers and the queue schema is in place."""
    database = queue = False
    try:
        await db.execute(text("SELECT 1"))
        database = True
        queue = bool(
            (
                await db.execute(text("SELECT to_regclass('procrastinate_jobs') IS NOT NULL"))
            ).scalar_one()
        )
    except Exception:  # readiness reports failure rather than raising
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    if not (database and queue):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessOut(
        status="ok" if database and queue else "unavailable", database=database, queue=queue
    )
