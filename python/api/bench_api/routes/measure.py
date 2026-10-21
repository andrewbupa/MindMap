"""Measure: Bloom behaviours, their scenario sets, suites, and elicitation rates."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import AsyncIterator, Iterable

from fastapi import APIRouter, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy import select

from bench_api.deps import AppSettings, AuthorUser, Db, ReaderUser
from bench_api.models_dep import Roles
from bench_api.run_control import cancel_run, status_events
from bench_api.schemas import (
    BehaviourDetail,
    BehaviourSummary,
    ElicitationOut,
    EpochTallyOut,
    GeneratedDimensionOut,
    GeneratedScenarioOut,
    MeasureLaunch,
    MeasureRunOut,
    MeasureRunSummary,
    RolloutOut,
    RunOut,
    SampleOut,
    ScenarioGenerate,
    ScenarioSetOut,
    ScenarioSetSummary,
    ScenarioTallyOut,
    TallyOut,
)
from bench_core import explore, queue
from bench_core.agents.load import AgentNotFound, load_agent_version
from bench_core.measure.behaviours import BehaviourError, BehaviourSource, load_behaviours
from bench_core.measure.rates import Elicitation, Rollout, Tally, elicitation
from bench_core.measure.suites import (
    PRESENCE_TAG,
    SCORE_SOURCE,
    MeasureError,
    MeasureOptions,
    create_generation_run,
    create_measure_run,
    scenario_ids,
    scenario_key,
    scenario_set_definition,
)
from bench_core.models import (
    Behaviour,
    Run,
    RunKind,
    RunSample,
    Scenario,
    ScenarioSet,
    Score,
    Transcript,
)
from bench_core.provenance import ProvenanceError, current_git_commit

router = APIRouter(prefix="/measure", tags=["measure"])

TOP_ROLLOUTS = 10
# Generated scenario rows carry their variation axis as a tag.
VARIATION = "variation:"


def _sources(settings: AppSettings) -> dict[str, BehaviourSource]:
    try:
        return load_behaviours(settings.repo_root)
    except BehaviourError as error:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(error)) from error


def _source(settings: AppSettings, key: str) -> BehaviourSource:
    source = _sources(settings).get(key)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No behaviour called {key}.")
    return source


def _set_summary(
    scenario_set: ScenarioSet, behaviour: Behaviour, run: Run, current_hash: str | None
) -> ScenarioSetSummary:
    return ScenarioSetSummary(
        id=scenario_set.id,
        run_id=scenario_set.run_id,
        behaviour_id=scenario_set.behaviour_id,
        created_at=scenario_set.created_at,
        scenario_count=scenario_set.scenario_count,
        presence_dimension=scenario_set.presence_dimension,
        content_hash=scenario_set.content_hash,
        behaviour_seed_hash=behaviour.seed_hash,
        current=behaviour.seed_hash == current_hash,
        model=run.model_ids.get("scenarios", ""),
    )


async def _sets_for(
    db: Db, key: str, current_hash: str | None
) -> list[tuple[ScenarioSetSummary, ScenarioSet]]:
    rows = (
        await db.execute(
            select(ScenarioSet, Behaviour, Run)
            .join(Behaviour, Behaviour.id == ScenarioSet.behaviour_id)
            .join(Run, Run.id == ScenarioSet.run_id)
            .where(Behaviour.key == key)
            .order_by(ScenarioSet.created_at.desc())
        )
    ).all()
    return [(_set_summary(s, b, r, current_hash), s) for s, b, r in rows]


async def _open_generation(db: Db, key: str) -> Run | None:
    return (
        await db.execute(
            select(Run)
            .where(Run.kind == RunKind.scenarios.value)
            .where(Run.status.in_(explore.OPEN))
            .where(Run.config["behaviour"].astext == key)
            .order_by(Run.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def _summary(
    source: BehaviourSource, latest: ScenarioSetSummary | None, generating: Run | None
) -> BehaviourSummary:
    definition = source.definition
    return BehaviourSummary(
        key=source.key,
        title=source.title,
        definition=definition.description,
        agents=source.agents,
        tags=list(definition.tags),
        variations=sorted(definition.variations),
        num_scenarios=definition.num_scenarios,
        scenario_type=source.scenario_type,
        content_notes=source.content_notes,
        seed_hash=source.seed_hash,
        scenario_set=latest,
        generating=RunOut.model_validate(generating) if generating else None,
    )


@router.get("/behaviours")
async def list_behaviours(_: ReaderUser, db: Db, settings: AppSettings) -> list[BehaviourSummary]:
    summaries = []
    for source in _sources(settings).values():
        sets = await _sets_for(db, source.key, source.seed_hash)
        current = next((summary for summary, _ in sets if summary.current), None)
        summaries.append(_summary(source, current, await _open_generation(db, source.key)))
    return summaries


def _tally(tally: Tally) -> TallyOut:
    return TallyOut(
        rollouts=tally.rollouts,
        elicited=tally.elicited,
        unscored=tally.unscored,
        rate=tally.rate,
        mean_score=tally.mean_score,
    )


def _elicitation(result: Elicitation) -> ElicitationOut:
    spread = result.spread
    return ElicitationOut(
        threshold=result.threshold,
        overall=_tally(result.overall),
        by_epoch=[
            EpochTallyOut(epoch=epoch, **_tally(tally).model_dump())
            for epoch, tally in result.by_epoch.items()
        ],
        spread_low=spread[0] if spread else None,
        spread_high=spread[1] if spread else None,
        stdev=result.stdev,
    )


async def measure_rollouts(db: Db, runs: Iterable[Run]) -> dict[uuid.UUID, list[RolloutOut]]:
    """Every indexed rollout of these Measure runs, with its presence score."""
    by_id = {run.id: run for run in runs}
    result: dict[uuid.UUID, list[RolloutOut]] = {run_id: [] for run_id in by_id}
    if not by_id:
        return result
    rows = (
        await db.execute(
            select(Transcript, Scenario)
            .outerjoin(Scenario, Scenario.id == Transcript.scenario_id)
            .where(Transcript.run_id.in_(by_id))
        )
    ).all()
    ids = [transcript.id for transcript, _ in rows]
    scores: dict[uuid.UUID, dict[str, Score]] = defaultdict(dict)
    if ids:
        for row in (
            await db.execute(
                select(Score).where(Score.transcript_id.in_(ids), Score.source == SCORE_SOURCE)
            )
        ).scalars():
            scores[row.transcript_id][row.dimension] = row
    for transcript, scenario in rows:
        run = by_id[transcript.run_id]
        config = run.config
        score = scores[transcript.id].get(config["presence_dimension"])
        tags = scenario.risk_tags if scenario else []
        variation = next((t.removeprefix(VARIATION) for t in tags if t.startswith(VARIATION)), None)
        result[run.id].append(
            RolloutOut(
                transcript_id=transcript.id,
                run_id=run.id,
                version=config["version"],
                sample_index=transcript.sample_index,
                epoch=transcript.epoch,
                scenario=config["seeds"][transcript.sample_index],
                variation=variation,
                score=score.value if score else None,
                score_id=score.id if score else None,
                summary=transcript.summary,
                content_notes=scenario.content_notes if scenario else [],
            )
        )
    for rollouts in result.values():
        rollouts.sort(key=lambda r: (-(r.score or 0), r.sample_index, r.epoch))
    return result


def measure_rates(run: Run, rollouts: list[RolloutOut]) -> Elicitation:
    return elicitation(
        (Rollout(scenario=r.scenario, epoch=r.epoch, score=r.score) for r in rollouts),
        threshold=float(run.config.get("threshold", 7)),
    )


async def _run_summary(db: Db, run: Run, rollouts: list[RolloutOut]) -> MeasureRunSummary:
    config = run.config
    return MeasureRunSummary(
        run=RunOut.model_validate(run),
        agent=config["agent"],
        version=config["version"],
        behaviour=config["behaviour"],
        scenario_set=uuid.UUID(config["scenario_set"]),
        suite=config["suite"],
        counts=await explore.sample_counts(db, run.id),
        elicitation=_elicitation(measure_rates(run, rollouts)),
    )


@router.get("/behaviours/{key}")
async def read_behaviour(
    key: str,
    _: ReaderUser,
    db: Db,
    settings: AppSettings,
    scenario_set: uuid.UUID | None = None,
) -> BehaviourDetail:
    source = _source(settings, key)
    sets = await _sets_for(db, key, source.seed_hash)
    current = next((summary for summary, _ in sets if summary.current), None)
    selected = scenario_set or (current.id if current else (sets[0][0].id if sets else None))
    generations = (
        (
            await db.execute(
                select(Run)
                .where(Run.kind == RunKind.scenarios.value)
                .where(Run.config["behaviour"].astext == key)
                .order_by(Run.created_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    runs: list[Run] = []
    if selected is not None:
        runs = list(
            (
                await db.execute(
                    select(Run)
                    .where(Run.kind == RunKind.measure.value)
                    .where(Run.config["scenario_set"].astext == str(selected))
                    .order_by(Run.created_at.desc())
                    .limit(100)
                )
            ).scalars()
        )
    rollouts = await measure_rollouts(db, runs)
    top = sorted(
        (r for run_rollouts in rollouts.values() for r in run_rollouts if r.score is not None),
        key=lambda r: -(r.score or 0),
    )[:TOP_ROLLOUTS]
    open_generation = next((run for run in generations if run.status in explore.OPEN), None)
    return BehaviourDetail(
        **_summary(source, current, open_generation).model_dump(),
        scenario_sets=[summary for summary, _ in sets],
        generations=[RunOut.model_validate(run) for run in generations],
        selected_set=selected,
        runs=[await _run_summary(db, run, rollouts[run.id]) for run in runs],
        top_rollouts=top,
    )


@router.post("/behaviours/{key}/scenario-sets", status_code=status.HTTP_201_CREATED)
async def generate_scenario_set(
    key: str,
    body: ScenarioGenerate,
    user: AuthorUser,
    db: Db,
    settings: AppSettings,
    roles: Roles,
) -> RunOut:
    """Run Bloom's understanding and ideation for the behaviour as it is in git now."""
    source = _source(settings, key)
    if await _open_generation(db, key) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Scenarios are already being generated.")
    try:
        run, sample = await create_generation_run(
            db,
            source=source,
            roles=roles,
            git_commit=current_git_commit(settings.repo_root, settings.git_commit),
            launched_by=user.id,
            token_budget=body.token_budget,
        )
    except (MeasureError, ProvenanceError) as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    await db.commit()
    sample.job_id = await queue.defer(
        "generate_scenarios", queue=queue.RUNS_QUEUE, run_sample_id=str(sample.id)
    )
    await db.commit()
    return RunOut.model_validate(run)


@router.get("/scenario-sets/{scenario_set_id}")
async def read_scenario_set(
    scenario_set_id: uuid.UUID, _: ReaderUser, db: Db, settings: AppSettings
) -> ScenarioSetOut:
    row = (
        await db.execute(
            select(ScenarioSet, Behaviour, Run)
            .join(Behaviour, Behaviour.id == ScenarioSet.behaviour_id)
            .join(Run, Run.id == ScenarioSet.run_id)
            .where(ScenarioSet.id == scenario_set_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such scenario set.")
    scenario_set, behaviour, run = row
    source = _sources(settings).get(behaviour.key)
    definition = scenario_set_definition(scenario_set)
    ids = scenario_ids(definition)
    keys = [scenario_key(behaviour.key, scenario_id) for scenario_id in ids]
    rows = {
        (s.key, s.seed_text): s.id
        for s in (await db.execute(select(Scenario).where(Scenario.key.in_(keys)))).scalars()
    }
    return ScenarioSetOut(
        summary=_set_summary(scenario_set, behaviour, run, source.seed_hash if source else None),
        behaviour=behaviour.key,
        understanding=definition.understanding,
        scientific_motivation=definition.scientific_motivation,
        scenarios=[
            GeneratedScenarioOut(
                id=scenario_id,
                name=scenario.name,
                variation=scenario.variation,
                seed=scenario.seed,
                scenario_row=rows.get((key, scenario.seed)),
            )
            for scenario_id, key, scenario in zip(
                ids, keys, definition.scenarios or [], strict=True
            )
        ],
        dimensions=[
            GeneratedDimensionOut(
                name=dimension.name,
                description=dimension.description,
                tags=list(dimension.tags),
                rubric=dimension.rubric,
                presence=PRESENCE_TAG in dimension.tags,
            )
            for dimension in definition.dimensions or []
        ],
        generation=RunOut.model_validate(run),
    )


@router.post("/runs", status_code=status.HTTP_201_CREATED)
async def launch_measure(
    body: MeasureLaunch, user: AuthorUser, db: Db, settings: AppSettings, roles: Roles
) -> list[RunOut]:
    """One run per prompt version, all against the same scenarios: a suite."""
    scenario_set = await db.get(ScenarioSet, body.scenario_set)
    if scenario_set is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such scenario set.")
    if len(set(body.versions)) != len(body.versions):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Each prompt version once, please.")
    suite_id = uuid.uuid4()
    commit = current_git_commit(settings.repo_root, settings.git_commit)
    created: list[tuple[Run, list[RunSample]]] = []
    try:
        for version in body.versions:
            stored = await load_agent_version(db, body.agent, version)
            created.append(
                await create_measure_run(
                    db,
                    stored=stored,
                    scenario_set=scenario_set,
                    roles=roles,
                    options=MeasureOptions(
                        epochs=body.epochs,
                        max_turns=body.max_turns,
                        token_budget=body.token_budget,
                        compaction=body.compaction,
                    ),
                    git_commit=commit,
                    launched_by=user.id,
                    suite_id=suite_id,
                )
            )
    except AgentNotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except (MeasureError, ProvenanceError) as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    await db.commit()
    for _run, samples in created:
        for sample in samples:
            sample.job_id = await queue.defer(
                "measure_sample", queue=queue.RUNS_QUEUE, run_sample_id=str(sample.id)
            )
    await db.commit()
    return [RunOut.model_validate(run) for run, _ in created]


@router.get("/runs")
async def list_measure_runs(
    _: ReaderUser, db: Db, behaviour: str | None = None
) -> list[MeasureRunSummary]:
    query = select(Run).where(Run.kind == RunKind.measure.value)
    if behaviour:
        query = query.where(Run.config["behaviour"].astext == behaviour)
    runs = list((await db.execute(query.order_by(Run.created_at.desc()).limit(100))).scalars())
    rollouts = await measure_rollouts(db, runs)
    return [await _run_summary(db, run, rollouts[run.id]) for run in runs]


async def _run_of(db: Db, run_id: uuid.UUID, *kinds: RunKind) -> Run:
    run = await db.get(Run, run_id)
    if run is None or run.kind not in {kind.value for kind in kinds}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Measure run.")
    return run


@router.get("/runs/{run_id}")
async def read_measure_run(run_id: uuid.UUID, _: ReaderUser, db: Db) -> MeasureRunOut:
    run = await _run_of(db, run_id, RunKind.measure)
    samples = (
        await db.execute(
            select(RunSample)
            .where(RunSample.run_id == run.id)
            .order_by(RunSample.epoch, RunSample.sample_index)
        )
    ).scalars()
    rollouts = (await measure_rollouts(db, [run]))[run.id]
    rates = measure_rates(run, rollouts)
    variations = {r.scenario: r.variation for r in rollouts}
    summary = await _run_summary(db, run, rollouts)
    return MeasureRunOut(
        **summary.model_dump(),
        samples=[SampleOut.model_validate(sample) for sample in samples],
        rollouts=rollouts,
        by_scenario=[
            ScenarioTallyOut(
                scenario=scenario,
                variation=variations.get(scenario),
                **_tally(rates.by_scenario[scenario]).model_dump(),
            )
            for scenario in run.config["seeds"]
            if scenario in rates.by_scenario
        ],
    )


@router.get("/runs/{run_id}/events", response_class=EventSourceResponse)
async def stream_measure_run(
    run_id: uuid.UUID, _: ReaderUser, db: Db
) -> AsyncIterator[ServerSentEvent]:
    """Sample counts as they change, for suites and scenario generation alike."""
    await _run_of(db, run_id, RunKind.measure, RunKind.scenarios)
    async for event in status_events(run_id):
        yield event


@router.post("/runs/{run_id}/cancel")
async def cancel_measure_run(run_id: uuid.UUID, user: AuthorUser, db: Db) -> RunOut:
    return await cancel_run(await _run_of(db, run_id, RunKind.measure, RunKind.scenarios), user, db)
