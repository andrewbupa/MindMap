"""Lens: launch panel readings of finished runs, and read what the panel found."""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import AsyncIterator, Iterable

from fastapi import APIRouter, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy import func, select

from agora_api.deps import AppSettings, AuthorUser, Db, ReaderUser
from agora_api.models_dep import Roles
from agora_api.routes.explore import _check_content_notes
from agora_api.run_control import cancel_run, status_events
from agora_api.schemas import (
    AnnotationOut,
    ConsensusOut,
    DroppedCountOut,
    ExpectationOut,
    FitOut,
    IntervalOut,
    JudgeCountOut,
    LabelComparisonOut,
    LabelPrevalenceOut,
    LensCompareOut,
    LensEvidenceOut,
    LensFamilyOut,
    LensLabelOut,
    LensLaunch,
    LensRunOut,
    LensRunSummary,
    LensSourceOut,
    LensTranscriptOut,
    LensTranscriptSummary,
    MessageOut,
    ReplyLensOut,
    RunOut,
    SampleOut,
    ScenarioComparisonOut,
    TaxonomyOut,
)
from agora_core import explore, queue
from agora_core.lens.panel import PanelError
from agora_core.lens.read import LabelInfo, RunLens, TranscriptLens, load_run_lens
from agora_core.lens.results import ReplyLens, mean_fit, prevalence
from agora_core.lens.runs import READABLE, LensError, create_lens_run
from agora_core.lens.taxonomy import TaxonomyError, load_lens
from agora_core.model_roles import ModelRolesError
from agora_core.models import (
    FINISHED_STATUSES,
    Label,
    Run,
    RunKind,
    RunSample,
    TaxonomyVersion,
    Transcript,
    User,
)
from agora_core.provenance import ProvenanceError, current_git_commit

router = APIRouter(prefix="/lens", tags=["lens"])


@router.get("/taxonomy")
async def read_taxonomy(_: ReaderUser, db: Db, settings: AppSettings) -> TaxonomyOut:
    """The taxonomy in git, with each label's trust status as stored."""
    spec = load_lens(settings.repo_root)
    taxonomy = spec.taxonomy
    stored = (
        await db.execute(
            select(Label.key, Label.trust_status)
            .join(TaxonomyVersion, TaxonomyVersion.id == Label.taxonomy_version_id)
            .where(TaxonomyVersion.version == taxonomy.version)
        )
    ).all()
    trust = {key: status_ for key, status_ in stored}
    return TaxonomyOut(
        version=taxonomy.version,
        families=[
            LensFamilyOut(key=key, name=family.name, source=family.source)
            for key, family in taxonomy.families.items()
        ],
        labels=[
            LensLabelOut(
                key=label.key,
                family=label.family,
                definition=" ".join(label.definition.split()),
                examples=list(label.examples),
                counter_examples=list(label.counter_examples),
                trust_status=trust.get(label.key, "unrated"),
            )
            for label in taxonomy.labels
        ],
    )


@router.get("/sources")
async def list_lens_sources(_: ReaderUser, db: Db) -> list[LensSourceOut]:
    """Finished runs whose transcripts Lens can read."""
    counts = (
        select(Transcript.run_id, func.count().label("n")).group_by(Transcript.run_id).subquery()
    )
    rows = (
        await db.execute(
            select(Run, counts.c.n)
            .join(counts, counts.c.run_id == Run.id)
            .where(Run.kind.in_(READABLE))
            .where(Run.status.in_([s.value for s in FINISHED_STATUSES]))
            .order_by(Run.created_at.desc())
            .limit(50)
        )
    ).all()
    return [LensSourceOut(run=RunOut.model_validate(run), transcripts=n) for run, n in rows]


@router.post("/runs", status_code=status.HTTP_201_CREATED)
async def launch_lens(
    body: LensLaunch, user: AuthorUser, db: Db, settings: AppSettings, roles: Roles
) -> RunOut:
    source = await db.get(Run, body.source_run)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such run.")
    try:
        run, samples = await create_lens_run(
            db,
            root=settings.repo_root,
            source=source,
            roles=roles,
            git_commit=current_git_commit(settings.repo_root, settings.git_commit),
            launched_by=user.id,
            transcript_ids=body.transcripts,
            token_budget=body.token_budget,
        )
    except (LensError, PanelError, ModelRolesError, TaxonomyError, ProvenanceError) as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    await db.commit()
    for sample in samples:
        sample.job_id = await queue.defer(
            "lens_sample", queue=queue.RUNS_QUEUE, run_sample_id=str(sample.id)
        )
    await db.commit()
    return RunOut.model_validate(run)


async def _lens_run(db: Db, run_id: uuid.UUID) -> Run:
    run = await db.get(Run, run_id)
    if run is None or run.kind != RunKind.lens.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Lens run.")
    return run


async def _source(db: Db, run: Run) -> Run:
    source = await db.get(Run, run.source_run_id) if run.source_run_id else None
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The Lens run's source is missing.")
    return source


def label_shares(replies: list[ReplyLens], labels: Iterable[LabelInfo]) -> list[LabelPrevalenceOut]:
    chosen = list(labels)
    shares = prevalence(replies, [label.key for label in chosen])
    result = []
    for label in chosen:
        share = shares[label.key]
        interval = share.interval
        result.append(
            LabelPrevalenceOut(
                label=label.key,
                family=label.family,
                trust_status=label.trust_status,
                replies=share.replies,
                expressed=share.expressed,
                share=share.share,
                interval=IntervalOut(low=interval[0], high=interval[1]) if interval else None,
                mean_intensity=share.mean_intensity,
                disputed=sum(1 for reply in replies if label.key in reply.disputed),
            )
        )
    return result


def _dropped(lens: RunLens, message_ids: set[uuid.UUID] | None = None) -> list[DroppedCountOut]:
    counts = Counter(
        (d.judge_model, d.reason)
        for d in lens.dropped
        if message_ids is None or d.message_id in message_ids
    )
    return [
        DroppedCountOut(judge=judge, reason=reason, count=n)
        for (judge, reason), n in sorted(counts.items())
    ]


async def _summary(db: Db, run: Run, lens: RunLens) -> LensRunSummary:
    return LensRunSummary(
        run=RunOut.model_validate(run),
        source=RunOut.model_validate(await _source(db, run)),
        counts=await explore.sample_counts(db, run.id),
        mean_fit=mean_fit(lens.replies),
    )


@router.get("/runs")
async def list_lens_runs(_: ReaderUser, db: Db) -> list[LensRunSummary]:
    runs = (
        await db.execute(
            select(Run)
            .where(Run.kind == RunKind.lens.value)
            .order_by(Run.created_at.desc())
            .limit(50)
        )
    ).scalars()
    return [await _summary(db, run, await load_run_lens(db, run)) for run in runs]


def _order(settings: AppSettings) -> list[str]:
    """Label keys in the taxonomy's order, family by family."""
    return [label.key for label in load_lens(settings.repo_root).taxonomy.labels]


def _visible(user: User, lens: RunLens) -> RunLens:
    """Leave out transcripts with content notes the reader has not opted in to."""
    if user.sensitive_opt_in:
        return lens
    lens.transcripts = [
        t for t in lens.transcripts if not (t.scenario and t.scenario.content_notes)
    ]
    return lens


@router.get("/runs/{run_id}")
async def read_lens_run(
    run_id: uuid.UUID, user: ReaderUser, db: Db, settings: AppSettings, label: str | None = None
) -> LensRunOut:
    run = await _lens_run(db, run_id)
    lens = _visible(user, await load_run_lens(db, run, order=_order(settings)))
    summary = await _summary(db, run, lens)
    samples = (
        await db.execute(
            select(RunSample).where(RunSample.run_id == run.id).order_by(RunSample.sample_index)
        )
    ).scalars()
    kept = Counter(e.judge for t in lens.transcripts for e in t.evidence)
    dropped = Counter(d.judge_model for d in lens.dropped)
    evidence = [
        LensEvidenceOut(
            id=uuid.UUID(e.id),
            transcript_id=t.transcript.id,
            message_id=uuid.UUID(e.message_id),
            label=e.label,
            judge=e.judge,
            intensity=e.intensity,
            quote=e.quote,
            channel=e.channel,
        )
        for t in lens.transcripts
        for e in t.evidence
        if label is not None and e.label == label
    ]
    return LensRunOut(
        **summary.model_dump(),
        judges=lens.judges,
        samples=[SampleOut.model_validate(sample) for sample in samples],
        labels=label_shares(lens.replies, lens.labels),
        transcripts=[
            LensTranscriptSummary(
                transcript_id=t.transcript.id,
                sample_index=t.transcript.sample_index,
                epoch=t.transcript.epoch,
                scenario_key=t.scenario.key if t.scenario else None,
                scenario_type=t.scenario.scenario_type if t.scenario else None,
                content_notes=t.scenario.content_notes if t.scenario else [],
                replies=len(t.replies),
                fit=t.fit,
                disputed=t.disputed,
            )
            for t in lens.transcripts
        ],
        judge_counts=[
            JudgeCountOut(judge=judge, kept=kept[judge], dropped=dropped[judge])
            for judge in lens.judges
        ],
        dropped=_dropped(lens),
        evidence=sorted(evidence, key=lambda e: -e.intensity),
    )


@router.get("/runs/{run_id}/transcripts/{transcript_id}")
async def read_lens_transcript(
    run_id: uuid.UUID, transcript_id: uuid.UUID, user: ReaderUser, db: Db, settings: AppSettings
) -> LensTranscriptOut:
    run = await _lens_run(db, run_id)
    lens = await load_run_lens(db, run, only=[transcript_id], order=_order(settings))
    if not lens.transcripts:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "This Lens run did not read that transcript."
        )
    (found,) = lens.transcripts
    _check_content_notes(user, found.scenario)
    families = {label.key: label.family for label in lens.labels}
    index = {str(m.id): m.index for m in found.messages}
    taxonomy = {label.key: label for label in load_lens(settings.repo_root).taxonomy.labels}
    return LensTranscriptOut(
        run=RunOut.model_validate(run),
        source=RunOut.model_validate(await _source(db, run)),
        transcript_id=found.transcript.id,
        scenario_key=found.scenario.key if found.scenario else None,
        scenario_type=found.scenario.scenario_type if found.scenario else None,
        seed_text=found.scenario.seed_text if found.scenario else None,
        content_notes=found.scenario.content_notes if found.scenario else [],
        judges=lens.judges,
        messages=[MessageOut.model_validate(m) for m in found.messages],
        replies=[
            ReplyLensOut(
                message_id=uuid.UUID(reply.message_id),
                index=index[reply.message_id],
                labels=[
                    ConsensusOut(
                        label=key,
                        family=families.get(key, ""),
                        median=c.median,
                        by_judge=c.by_judge,
                        disputed=c.disputed,
                    )
                    for key, c in sorted(reply.labels.items())
                ],
                fit=FitOut(
                    score=reply.fit.score,
                    matches=reply.fit.matches,
                    misses=reply.fit.misses,
                    intrusions=reply.fit.intrusions,
                    out_of_band=reply.fit.out_of_band,
                )
                if reply.fit
                else None,
            )
            for reply in found.replies
        ],
        annotations=[
            AnnotationOut(
                id=uuid.UUID(e.id),
                message_id=uuid.UUID(e.message_id),
                label=e.label,
                family=families.get(e.label, ""),
                judge=e.judge,
                intensity=e.intensity,
                quote=e.quote,
                start=e.start,
                end=e.end,
                channel=e.channel,
                rationale=e.rationale,
            )
            for e in sorted(found.evidence, key=lambda e: (index[e.message_id], e.start))
        ],
        expected=[
            ExpectationOut(
                label=key,
                family=families.get(key, ""),
                expect=expect.expect,
                min=expect.min,
                max=expect.max,
            )
            for key, expect in sorted((found.expected or {}).items())
        ],
        labels=[
            LensLabelOut(
                key=label.key,
                family=label.family,
                definition=" ".join(label.definition.split()),
                examples=list(taxonomy[label.key].examples) if label.key in taxonomy else [],
                counter_examples=list(taxonomy[label.key].counter_examples)
                if label.key in taxonomy
                else [],
                trust_status=label.trust_status,
            )
            for label in lens.labels
        ],
        dropped=_dropped(lens, {m.id for m in found.messages}),
    )


@router.get("/compare")
async def compare_lens_runs(
    a: uuid.UUID, b: uuid.UUID, user: ReaderUser, db: Db, settings: AppSettings
) -> LensCompareOut:
    """Prompt A beside prompt B, on the scenarios both runs read."""
    run_a, run_b = await _lens_run(db, a), await _lens_run(db, b)
    if run_a.taxonomy_version != run_b.taxonomy_version:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "These runs used different taxonomy versions."
        )
    order = _order(settings)
    lens_a = _visible(user, await load_run_lens(db, run_a, order=order))
    lens_b = _visible(user, await load_run_lens(db, run_b, order=order))

    def keyed(lens: RunLens) -> dict[str, list[TranscriptLens]]:
        grouped: dict[str, list[TranscriptLens]] = {}
        for t in lens.transcripts:
            if t.scenario:
                grouped.setdefault(t.scenario.key, []).append(t)
        return grouped

    groups_a, groups_b = keyed(lens_a), keyed(lens_b)
    shared = sorted(set(groups_a) & set(groups_b))
    replies_a = [r for key in shared for t in groups_a[key] for r in t.replies]
    replies_b = [r for key in shared for t in groups_b[key] for r in t.replies]
    side_a = {p.label: p for p in label_shares(replies_a, lens_a.labels)}
    side_b = {p.label: p for p in label_shares(replies_b, lens_b.labels)}
    labels = []
    for label in lens_a.labels:
        if label.key not in side_b:
            continue
        left, right = side_a[label.key].share, side_b[label.key].share
        labels.append(
            LabelComparisonOut(
                label=label.key,
                family=label.family,
                a=side_a[label.key],
                b=side_b[label.key],
                difference=right - left if left is not None and right is not None else None,
            )
        )
    return LensCompareOut(
        a=await _summary(db, run_a, lens_a),
        b=await _summary(db, run_b, lens_b),
        shared_scenarios=len(shared),
        labels=labels,
        scenarios=[
            ScenarioComparisonOut(
                scenario_key=key,
                a_fit=mean_fit([r for t in groups_a[key] for r in t.replies]),
                b_fit=mean_fit([r for t in groups_b[key] for r in t.replies]),
                a_transcripts=[t.transcript.id for t in groups_a[key]],
                b_transcripts=[t.transcript.id for t in groups_b[key]],
            )
            for key in shared
        ],
    )


@router.get("/runs/{run_id}/events", response_class=EventSourceResponse)
async def stream_lens_run(
    run_id: uuid.UUID, _: ReaderUser, db: Db
) -> AsyncIterator[ServerSentEvent]:
    await _lens_run(db, run_id)
    async for event in status_events(run_id):
        yield event


@router.post("/runs/{run_id}/cancel")
async def cancel_lens_run(run_id: uuid.UUID, user: AuthorUser, db: Db) -> RunOut:
    return await cancel_run(await _lens_run(db, run_id), user, db)
