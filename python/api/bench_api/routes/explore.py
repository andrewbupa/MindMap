"""Explore: launch Petri audits, follow them, and read scored transcripts."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy import select

from bench_api.deps import AppSettings, AuthorUser, Db, ReaderUser
from bench_api.models_dep import Roles
from bench_api.schemas import (
    ExploreLaunch,
    ExploreRunOut,
    MessageOut,
    RunOut,
    SampleOut,
    ScoreOut,
    SeedOut,
    TranscriptOut,
    TranscriptSummary,
)
from bench_core import audit, explore, queue
from bench_core.agents.load import AgentNotFound, load_agent_version
from bench_core.db import get_sessionmaker
from bench_core.models import (
    Message,
    Role,
    Run,
    RunKind,
    RunSample,
    RunStatus,
    Scenario,
    Score,
    Transcript,
    User,
)
from bench_core.provenance import ProvenanceError, current_git_commit
from bench_core.seeds import SeedError, dimension_names, load_seeds, select_seeds

router = APIRouter(prefix="/explore", tags=["explore"])

STREAM_SECONDS = 85
POLL_SECONDS = 2.0


@router.get("/seeds")
async def list_seeds(
    _: ReaderUser, settings: AppSettings, agent: str | None = None
) -> list[SeedOut]:
    seeds = load_seeds(settings.repo_root).values()
    return [
        SeedOut(
            key=seed.key,
            title=seed.title,
            tags=seed.tags,
            agents=seed.agents,
            scenario_type=seed.scenario_type,
            content_notes=seed.content_notes,
            text=seed.text,
            sha256=seed.sha256,
        )
        for seed in seeds
        if agent is None or not seed.agents or agent in seed.agents
    ]


@router.post("/runs", status_code=status.HTTP_201_CREATED)
async def launch(
    body: ExploreLaunch, user: AuthorUser, db: Db, settings: AppSettings, roles: Roles
) -> RunOut:
    try:
        stored = await load_agent_version(db, body.agent, body.version)
    except AgentNotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    try:
        seeds = select_seeds(
            load_seeds(settings.repo_root), agent=body.agent, keys=body.seeds, tags=body.tags
        )
        run, samples = await explore.create_run(
            db,
            root=settings.repo_root,
            stored=stored,
            seeds=seeds,
            roles=roles,
            options=explore.ExploreOptions(
                max_turns=body.max_turns, epochs=body.epochs, token_budget=body.token_budget
            ),
            git_commit=current_git_commit(settings.repo_root, settings.git_commit),
            launched_by=user.id,
        )
    except (SeedError, explore.ExploreError, ProvenanceError) as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    await db.commit()
    for sample in samples:
        sample.job_id = await queue.defer(
            "explore_sample", queue=queue.RUNS_QUEUE, run_sample_id=str(sample.id)
        )
    await db.commit()
    return RunOut.model_validate(run)


@router.get("/runs")
async def list_runs(_: ReaderUser, db: Db) -> list[RunOut]:
    runs = (
        await db.execute(
            select(Run)
            .where(Run.kind == RunKind.explore.value)
            .order_by(Run.created_at.desc())
            .limit(100)
        )
    ).scalars()
    return [RunOut.model_validate(run) for run in runs]


async def _explore_run(db: Db, run_id: uuid.UUID) -> Run:
    run = await db.get(Run, run_id)
    if run is None or run.kind != RunKind.explore.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Explore run.")
    return run


async def _transcripts(db: Db, run: Run) -> list[TranscriptSummary]:
    rows = (
        await db.execute(
            select(Transcript, Scenario)
            .outerjoin(Scenario, Scenario.id == Transcript.scenario_id)
            .where(Transcript.run_id == run.id)
            .order_by(Transcript.sample_index, Transcript.epoch)
        )
    ).all()
    ids = [transcript.id for transcript, _ in rows]
    scores: dict[uuid.UUID, dict[str, float]] = {tid: {} for tid in ids}
    if ids:
        for score in (
            await db.execute(select(Score).where(Score.transcript_id.in_(ids)))
        ).scalars():
            scores[score.transcript_id][score.dimension] = score.value
    return [
        TranscriptSummary(
            id=transcript.id,
            sample_index=transcript.sample_index,
            epoch=transcript.epoch,
            scenario_key=scenario.key if scenario else None,
            summary=transcript.summary,
            content_notes=scenario.content_notes if scenario else [],
            scores=scores[transcript.id],
        )
        for transcript, scenario in rows
    ]


@router.get("/runs/{run_id}")
async def read_run(
    run_id: uuid.UUID, _: ReaderUser, db: Db, settings: AppSettings
) -> ExploreRunOut:
    run = await _explore_run(db, run_id)
    samples = (
        (
            await db.execute(
                select(RunSample)
                .where(RunSample.run_id == run.id)
                .order_by(RunSample.epoch, RunSample.sample_index)
            )
        )
        .scalars()
        .all()
    )
    transcripts = await _transcripts(db, run)
    seen = sorted({dimension for t in transcripts for dimension in t.scores})
    custom = dimension_names(settings.repo_root)
    dimensions = [d for d in custom if d in seen or not seen] + [d for d in seen if d not in custom]
    return ExploreRunOut(
        run=RunOut.model_validate(run),
        agent=run.config["agent"],
        version=run.config["version"],
        seeds=run.config["seeds"],
        samples=[SampleOut.model_validate(sample) for sample in samples],
        counts=await explore.sample_counts(db, run.id),
        dimensions=dimensions,
        transcripts=transcripts,
    )


@router.get("/runs/{run_id}/events", response_class=EventSourceResponse)
async def stream_run(run_id: uuid.UUID, _: ReaderUser, db: Db) -> AsyncIterator[ServerSentEvent]:
    """Sample counts as they change. Clients reconnect after the stream ends, or poll."""
    await _explore_run(db, run_id)
    last: dict[str, object] | None = None
    for _tick in range(int(STREAM_SECONDS / POLL_SECONDS)):
        async with get_sessionmaker()() as fresh:
            run = await fresh.get(Run, run_id)
            if run is None:
                return
            state: dict[str, object] = {
                "status": run.status,
                "tokens_used": run.tokens_used,
                "counts": await explore.sample_counts(fresh, run_id),
            }
        if state != last:
            last = state
            yield ServerSentEvent(data=state, event="status", retry=3000)
        if state["status"] not in explore.OPEN:
            return
        await asyncio.sleep(POLL_SECONDS)


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: uuid.UUID, user: AuthorUser, db: Db) -> RunOut:
    run = await _explore_run(db, run_id)
    if run.launched_by != user.id and not user.has_role(Role.admin):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the person who launched this can cancel it."
        )
    if run.status not in explore.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, "This run has already finished.")
    run.status = RunStatus.cancelled.value
    run.finished_at = datetime.now(UTC)
    await audit.record(db, "run.cancel", actor_id=user.id, target_type="run", target_id=run.id)
    await db.commit()
    return RunOut.model_validate(run)


@router.get("/transcripts/{transcript_id}")
async def read_transcript(transcript_id: uuid.UUID, user: ReaderUser, db: Db) -> TranscriptOut:
    transcript = await db.get(Transcript, transcript_id)
    if transcript is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such transcript.")
    run = await db.get(Run, transcript.run_id)
    assert run is not None
    scenario = await db.get(Scenario, transcript.scenario_id) if transcript.scenario_id else None
    _check_content_notes(user, scenario)
    messages = (
        await db.execute(
            select(Message).where(Message.transcript_id == transcript.id).order_by(Message.index)
        )
    ).scalars()
    scores = (
        await db.execute(
            select(Score).where(Score.transcript_id == transcript.id).order_by(Score.dimension)
        )
    ).scalars()
    return TranscriptOut(
        id=transcript.id,
        run=RunOut.model_validate(run),
        sample_index=transcript.sample_index,
        epoch=transcript.epoch,
        scenario_key=scenario.key if scenario else None,
        seed_text=scenario.seed_text if scenario else None,
        content_notes=scenario.content_notes if scenario else [],
        summary=transcript.summary,
        messages=[MessageOut.model_validate(message) for message in messages],
        scores=[ScoreOut.model_validate(score) for score in scores],
    )


def _check_content_notes(user: User, scenario: Scenario | None) -> None:
    """Reviewer care: transcripts with content notes open only for people who opted in."""
    if scenario and scenario.content_notes and not user.sensitive_opt_in:
        notes = ", ".join(note.replace("_", " ") for note in scenario.content_notes)
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"This transcript has a content note ({notes}). Opt in under Settings, preferences"
            " to read transcripts like this.",
        )
