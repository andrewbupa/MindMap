"""Explore: launch Petri audits, follow them, and read scored transcripts."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from inspect_petri import judge_dimensions
from sqlalchemy import select

from agora_api.deps import AppSettings, AuthorUser, Db, OversightUser, ReaderUser
from agora_api.models_dep import Roles
from agora_api.run_control import cancel_run, status_events
from agora_api.schemas import (
    DimensionOut,
    ExploreLaunch,
    ExploreRunOut,
    FullThinkingOut,
    JudgeReference,
    MessageOut,
    RunOut,
    SampleOut,
    ScoreOut,
    SeedOut,
    SignedUrlOut,
    TranscriptOut,
    TranscriptSummary,
)
from agora_core import audit, explore, queue
from agora_core.agents.load import AgentNotFound, load_agent_version
from agora_core.models import (
    Message,
    Run,
    RunKind,
    RunSample,
    Scenario,
    Score,
    Transcript,
    User,
)
from agora_core.provenance import ProvenanceError, current_git_commit
from agora_core.seeds import SeedError, dimension_names, dimensions_dir, load_seeds, select_seeds
from agora_core.storage import get_storage
from agora_core.transcripts import key_from_uri

router = APIRouter(prefix="/explore", tags=["explore"])


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


@router.get("/dimensions")
async def list_dimensions(_: ReaderUser, settings: AppSettings) -> list[DimensionOut]:
    """Our dimensions first, then Petri's built-in ones."""
    ours = judge_dimensions(dimensions_dir(settings.repo_root))
    custom = {dimension.name for dimension in ours}
    return [
        DimensionOut(
            name=dimension.name,
            display_name=dimension.display_name or dimension.name.replace("_", " ").capitalize(),
            description=dimension.description,
            palette=dimension.palette,
            custom=dimension.name in custom,
            tags=list(dimension.tags),
        )
        for dimension in [*ours, *judge_dimensions()]
    ]


@router.post("/runs", status_code=status.HTTP_201_CREATED)
async def launch_explore(
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
                max_turns=body.max_turns,
                epochs=body.epochs,
                token_budget=body.token_budget,
                compaction=body.compaction,
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
async def list_explore_runs(_: ReaderUser, db: Db) -> list[RunOut]:
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
async def read_explore_run(
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
async def stream_explore_run(
    run_id: uuid.UUID, _: ReaderUser, db: Db
) -> AsyncIterator[ServerSentEvent]:
    """Sample counts as they change. Clients reconnect after the stream ends, or poll."""
    await _explore_run(db, run_id)
    async for event in status_events(run_id):
        yield event


@router.post("/runs/{run_id}/cancel")
async def cancel_explore_run(run_id: uuid.UUID, user: AuthorUser, db: Db) -> RunOut:
    return await cancel_run(await _explore_run(db, run_id), user, db)


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
        highlights=transcript.meta.get("highlights"),
        references=[
            JudgeReference.model_validate(reference)
            for reference in transcript.meta.get("judge_references", [])
        ],
        judge_refused=bool(transcript.meta.get("judge_refused")),
        messages=[MessageOut.model_validate(message) for message in messages],
        scores=[ScoreOut.model_validate(score) for score in scores],
    )


@router.get("/transcripts/{transcript_id}/log")
async def transcript_log(transcript_id: uuid.UUID, user: ReaderUser, db: Db) -> SignedUrlOut:
    """A short-lived link to the sample's Inspect log, for opening in Inspect View."""
    transcript = await db.get(Transcript, transcript_id)
    if transcript is None or not transcript.log_uri:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No log for this transcript.")
    scenario = await db.get(Scenario, transcript.scenario_id) if transcript.scenario_id else None
    _check_content_notes(user, scenario)
    storage = get_storage()
    key = key_from_uri(transcript.log_uri)
    await audit.record(
        db,
        "storage.signed_url",
        actor_id=user.id,
        target_type="transcript",
        target_id=transcript.id,
        detail={"key": key},
    )
    await db.commit()
    return SignedUrlOut(
        url=storage.signed_url(key, filename=f"{transcript.id}.eval"),
        expires_in=storage.signed_url_seconds,
    )


@router.get("/transcripts/{transcript_id}/thinking")
async def read_full_thinking(
    transcript_id: uuid.UUID, user: OversightUser, db: Db
) -> list[FullThinkingOut]:
    """Full thinking, where Anthropic granted it: for admins and compliance only, and
    every read is audited. Lens never reads it."""
    transcript = await db.get(Transcript, transcript_id)
    if transcript is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such transcript.")
    scenario = await db.get(Scenario, transcript.scenario_id) if transcript.scenario_id else None
    _check_content_notes(user, scenario)
    rows = (
        await db.execute(
            select(Message)
            .where(Message.transcript_id == transcript.id, Message.thinking_full.is_not(None))
            .order_by(Message.index)
        )
    ).scalars()
    found = [
        FullThinkingOut(message_id=m.id, index=m.index, thinking_full=m.thinking_full or "")
        for m in rows
    ]
    await audit.record(
        db,
        "transcript.full_thinking",
        actor_id=user.id,
        target_type="transcript",
        target_id=transcript.id,
        detail={"messages": len(found)},
    )
    await db.commit()
    return found


def _check_content_notes(user: User, scenario: Scenario | None) -> None:
    """Reviewer care: transcripts with content notes open only for people who opted in."""
    if scenario and scenario.content_notes and not user.sensitive_opt_in:
        notes = ", ".join(note.replace("_", " ") for note in scenario.content_notes)
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"This transcript has a content note ({notes}). Opt in under Settings, preferences"
            " to read transcripts like this.",
        )
