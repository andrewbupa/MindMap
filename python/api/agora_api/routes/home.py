"""Home: the week in review. New runs, prompt versions whose Tally rate rose over the
version before, and what is waiting for the reader in Jury."""

from __future__ import annotations

import re
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from itertools import pairwise

from fastapi import APIRouter
from sqlalchemy import select

from agora_api.deps import AppSettings, Db, ReaderUser
from agora_api.routes import gold, jury
from agora_api.routes.tally import tally_rates, tally_rollouts
from agora_api.schemas import AwaitingOut, RegressionOut, RunOut, WeekOut
from agora_core.models import GoldSet, Role, Run, RunKind, RunStatus
from agora_core.tally.behaviours import BehaviourError, load_behaviours

router = APIRouter(prefix="/home", tags=["home"])

WEEK = timedelta(days=7)
RECENT = 8
# Enough to say "50 or more" without reading every queue in full.
QUEUE_CAP = 50
# Runs whose numbers stand: a run stopped at its budget keeps what it scored.
RATED = [RunStatus.succeeded.value, RunStatus.stopped_at_budget.value]


def _version_key(version: str) -> tuple[list[int], str]:
    return [int(part) for part in re.findall(r"\d+", version)], version


async def _regressions(db: Db, settings: AppSettings, since: datetime) -> list[RegressionOut]:
    """Compare the newest finished run of each prompt version with the version before it,
    on the same behaviour, agent and scenario set, where the newer run finished this week."""
    recent = (
        await db.execute(
            select(Run).where(
                Run.kind == RunKind.tally.value,
                Run.status.in_(RATED),
                Run.finished_at >= since,
            )
        )
    ).scalars()
    groups = {(r.config["behaviour"], r.config["agent"], r.config["scenario_set"]) for r in recent}
    if not groups:
        return []
    runs = list(
        (
            await db.execute(
                select(Run).where(
                    Run.kind == RunKind.tally.value,
                    Run.status.in_(RATED),
                    Run.config["behaviour"].astext.in_({g[0] for g in groups}),
                )
            )
        ).scalars()
    )
    rollouts = await tally_rollouts(db, runs)
    latest: dict[tuple[str, str, str], dict[str, Run]] = defaultdict(dict)
    for run in runs:
        group = (run.config["behaviour"], run.config["agent"], run.config["scenario_set"])
        if group not in groups:
            continue
        seen = latest[group].get(run.config["version"])
        if seen is None or seen.created_at < run.created_at:
            latest[group][run.config["version"]] = run
    try:
        titles = {key: source.title for key, source in load_behaviours(settings.repo_root).items()}
    except BehaviourError:
        titles = {}
    found: list[RegressionOut] = []
    for (behaviour, agent, scenario_set), by_version in latest.items():
        ordered = sorted(by_version.items(), key=lambda item: _version_key(item[0]))
        for (before, earlier), (version, later) in pairwise(ordered):
            if later.finished_at is None or later.finished_at < since:
                continue
            rate = tally_rates(later, rollouts[later.id]).overall.rate
            previous = tally_rates(earlier, rollouts[earlier.id]).overall.rate
            if rate is None or previous is None or rate <= previous:
                continue
            found.append(
                RegressionOut(
                    behaviour=behaviour,
                    behaviour_title=titles.get(behaviour, behaviour.replace("_", " ").capitalize()),
                    agent=agent,
                    scenario_set=uuid.UUID(scenario_set),
                    version=version,
                    run_id=later.id,
                    rate=rate,
                    previous_version=before,
                    previous_run_id=earlier.id,
                    previous_rate=previous,
                )
            )
    return sorted(found, key=lambda r: r.previous_rate - r.rate)


@router.get("/week")
async def week_in_review(user: ReaderUser, db: Db, settings: AppSettings) -> WeekOut:
    since = datetime.now(UTC) - WEEK
    started = list(
        (
            await db.execute(
                select(Run).where(Run.created_at >= since).order_by(Run.created_at.desc())
            )
        ).scalars()
    )
    awaiting = None
    if user.has_role(Role.reviewer):
        scores = await jury.score_queue(user, db, settings, limit=QUEUE_CAP)
        ethos = await jury.ethos_queue(user, db, settings, limit=QUEUE_CAP)
        sets = (await db.execute(select(GoldSet))).scalars()
        summaries = [await gold.gold_summary(db, gold_set, user) for gold_set in sets]
        awaiting = AwaitingOut(
            scores=len(scores.items),
            ethos=len(ethos.items),
            gold=sum(s.items - s.labelled_by_me for s in summaries),
            capped=len(scores.items) >= QUEUE_CAP or len(ethos.items) >= QUEUE_CAP,
            hidden_for_content_notes=scores.hidden_for_content_notes
            + ethos.hidden_for_content_notes,
        )
    return WeekOut(
        since=since,
        runs=[RunOut.model_validate(run) for run in started[:RECENT]],
        by_kind=dict(Counter(run.kind for run in started)),
        finished=sum(1 for run in started if run.status in RATED),
        failed=sum(1 for run in started if run.status == RunStatus.failed.value),
        regressions=await _regressions(db, settings, since),
        awaiting=awaiting,
    )
