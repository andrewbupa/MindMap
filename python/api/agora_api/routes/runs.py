from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from agora_api.deps import AppSettings, Db, ReaderUser
from agora_api.models_dep import Roles
from agora_api.schemas import (
    KindSpendOut,
    MonthSpendOut,
    RunEstimateOut,
    RunOut,
    SignedUrlOut,
    SpendOut,
)
from agora_core import audit
from agora_core.model_roles import DEV_FAMILIES
from agora_core.models import FINISHED_STATUSES, Run, RunKind, RunSample
from agora_core.storage import get_storage
from agora_core.transcripts import key_from_uri

router = APIRouter(prefix="/runs", tags=["runs"])

# How many recent finished runs an estimate draws on.
ESTIMATE_BASIS = 20


def started_month(time_zone: str) -> Any:
    """The month a run started, as YYYY-MM in the given zone."""
    return func.to_char(func.timezone(time_zone, Run.created_at), "YYYY-MM")


def _months_back(now: datetime, count: int) -> list[str]:
    year, month = now.year, now.month
    months = []
    for _ in range(count):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    return months


@router.get("/spend")
async def spend(
    _: ReaderUser,
    db: Db,
    settings: AppSettings,
    roles: Roles,
    months: int = Query(default=6, ge=1, le=24),
) -> SpendOut:
    """Estimated spend by the month runs started, from each run's tokens and the prices
    in config/models.yaml."""
    zone = ZoneInfo(settings.time_zone)
    wanted = _months_back(datetime.now(UTC).astimezone(zone), months)
    month = started_month(settings.time_zone)
    rows = (
        await db.execute(
            select(
                month.label("month"),
                Run.kind,
                func.count(),
                func.coalesce(func.sum(Run.tokens_used), 0),
                func.coalesce(func.sum(Run.cost_usd), 0),
            )
            .where(month.in_(wanted))
            .group_by(month, Run.kind)
        )
    ).all()
    by_month: dict[str, dict[str, KindSpendOut]] = defaultdict(dict)
    for name, kind, runs, tokens, cost in rows:
        by_month[name][kind] = KindSpendOut(runs=runs, tokens=int(tokens), cost_usd=float(cost))
    used = {role.model for role in roles.roles.values() if role.family not in DEV_FAMILIES}
    return SpendOut(
        time_zone=settings.time_zone,
        months=[
            MonthSpendOut(
                month=name,
                runs=sum(k.runs for k in by_month[name].values()),
                tokens=sum(k.tokens for k in by_month[name].values()),
                cost_usd=round(sum(k.cost_usd for k in by_month[name].values()), 4),
                by_kind=dict(sorted(by_month[name].items())),
            )
            for name in wanted
        ],
        unpriced_models=sorted(used - set(roles.prices)),
    )


@router.get("/estimate")
async def estimate_run(
    _: ReaderUser, db: Db, roles: Roles, kind: RunKind, samples: int = Query(ge=1, le=100_000)
) -> RunEstimateOut:
    """What a launch of this many samples is likely to use, from recent finished runs of the
    same kind: their tokens and recorded cost per finished sample."""
    recent = (
        await db.execute(
            select(Run.id, Run.tokens_used, Run.cost_usd)
            .where(Run.kind == kind.value, Run.status.in_([s.value for s in FINISHED_STATUSES]))
            .where(Run.tokens_used > 0)
            .order_by(Run.finished_at.desc())
            .limit(ESTIMATE_BASIS)
        )
    ).all()
    budget = roles.budget(kind.value)
    if not recent:
        return RunEstimateOut(
            kind=kind.value, samples=samples, basis_runs=0, basis_samples=0, default_budget=budget
        )
    finished = (
        await db.execute(
            select(func.count())
            .select_from(RunSample)
            .where(RunSample.run_id.in_([row.id for row in recent]))
            .where(RunSample.tokens_used > 0)
        )
    ).scalar_one()
    tokens = sum(row.tokens_used for row in recent)
    cost = sum(float(row.cost_usd) for row in recent)
    per_tokens = tokens / finished if finished else None
    per_cost = cost / finished if finished else None
    return RunEstimateOut(
        kind=kind.value,
        samples=samples,
        basis_runs=len(recent),
        basis_samples=finished,
        tokens_per_sample=round(per_tokens) if per_tokens is not None else None,
        cost_per_sample_usd=per_cost,
        estimated_tokens=round(per_tokens * samples) if per_tokens is not None else None,
        estimated_cost_usd=per_cost * samples if per_cost is not None else None,
        default_budget=budget,
    )


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
