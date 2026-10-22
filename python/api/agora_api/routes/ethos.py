"""Ethos: launch panel readings of finished runs, and read what the panel found."""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import AsyncIterator, Iterable

from fastapi import APIRouter, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy import func, select

from agora_api.deps import AppSettings, AuthorUser, Db, ReaderUser
from agora_api.models_dep import Roles
from agora_api.routes.inquiry import _check_content_notes
from agora_api.run_control import cancel_run, status_events
from agora_api.schemas import (
    AnnotationOut,
    ConsensusOut,
    DroppedCountOut,
    EthosCompareOut,
    EthosEvidenceOut,
    EthosFamilyOut,
    EthosLabelOut,
    EthosLaunch,
    EthosRunOut,
    EthosRunSummary,
    EthosSourceOut,
    EthosTranscriptOut,
    EthosTranscriptSummary,
    ExpectationOut,
    FitOut,
    IntervalOut,
    JudgeCountOut,
    LabelComparisonOut,
    LabelPrevalenceOut,
    MessageOut,
    ReplyEthosOut,
    RunOut,
    SampleOut,
    ScenarioComparisonOut,
    TaxonomyOut,
)
from agora_core import inquiry, queue
from agora_core.ethos.panel import PanelError
from agora_core.ethos.read import LabelInfo, ResponseView, RunEthos, load_run_ethos
from agora_core.ethos.results import ReplyEthos, mean_fit, prevalence
from agora_core.ethos.runs import READABLE, EthosError, create_ethos_run
from agora_core.ethos.taxonomy import TaxonomyError, load_ethos
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

router = APIRouter(prefix="/ethos", tags=["ethos"])


@router.get("/taxonomy")
async def read_taxonomy(_: ReaderUser, db: Db, settings: AppSettings) -> TaxonomyOut:
    """The taxonomy in git, with each label's trust status as stored."""
    spec = load_ethos(settings.repo_root)
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
            EthosFamilyOut(key=key, name=family.name, source=family.source)
            for key, family in taxonomy.families.items()
        ],
        labels=[
            EthosLabelOut(
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
async def list_ethos_sources(_: ReaderUser, db: Db) -> list[EthosSourceOut]:
    """Finished runs whose transcripts Ethos can read."""
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
    return [EthosSourceOut(run=RunOut.model_validate(run), transcripts=n) for run, n in rows]


@router.post("/runs", status_code=status.HTTP_201_CREATED)
async def launch_ethos(
    body: EthosLaunch, user: AuthorUser, db: Db, settings: AppSettings, roles: Roles
) -> RunOut:
    source = await db.get(Run, body.source_run)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such run.")
    try:
        run, samples = await create_ethos_run(
            db,
            root=settings.repo_root,
            source=source,
            roles=roles,
            git_commit=current_git_commit(settings.repo_root, settings.git_commit),
            launched_by=user.id,
            transcript_ids=body.transcripts,
            token_budget=body.token_budget,
        )
    except (EthosError, PanelError, ModelRolesError, TaxonomyError, ProvenanceError) as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    await db.commit()
    for sample in samples:
        sample.job_id = await queue.defer(
            "ethos_sample", queue=queue.RUNS_QUEUE, run_sample_id=str(sample.id)
        )
    await db.commit()
    return RunOut.model_validate(run)


async def _ethos_run(db: Db, run_id: uuid.UUID) -> Run:
    run = await db.get(Run, run_id)
    if run is None or run.kind != RunKind.ethos.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Ethos run.")
    return run


async def _source(db: Db, run: Run) -> Run:
    source = await db.get(Run, run.source_run_id) if run.source_run_id else None
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The Ethos run's source is missing.")
    return source


def label_shares(
    replies: list[ReplyEthos], labels: Iterable[LabelInfo]
) -> list[LabelPrevalenceOut]:
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


def _dropped(ethos: RunEthos, message_ids: set[uuid.UUID] | None = None) -> list[DroppedCountOut]:
    counts = Counter(
        (d.judge_model, d.reason)
        for d in ethos.dropped
        if message_ids is None or d.message_id in message_ids
    )
    return [
        DroppedCountOut(judge=judge, reason=reason, count=n)
        for (judge, reason), n in sorted(counts.items())
    ]


async def _summary(db: Db, run: Run, ethos: RunEthos) -> EthosRunSummary:
    return EthosRunSummary(
        run=RunOut.model_validate(run),
        source=RunOut.model_validate(await _source(db, run)),
        counts=await inquiry.sample_counts(db, run.id),
        mean_fit=mean_fit(ethos.replies),
    )


@router.get("/runs")
async def list_ethos_runs(_: ReaderUser, db: Db) -> list[EthosRunSummary]:
    runs = (
        await db.execute(
            select(Run)
            .where(Run.kind == RunKind.ethos.value)
            .order_by(Run.created_at.desc())
            .limit(50)
        )
    ).scalars()
    return [await _summary(db, run, await load_run_ethos(db, run)) for run in runs]


def _order(settings: AppSettings) -> list[str]:
    """Label keys in the taxonomy's order, family by family."""
    return [label.key for label in load_ethos(settings.repo_root).taxonomy.labels]


def _visible(user: User, ethos: RunEthos) -> RunEthos:
    """Leave out transcripts with content notes the reader has not opted in to."""
    if user.sensitive_opt_in:
        return ethos
    ethos.transcripts = [
        t for t in ethos.transcripts if not (t.scenario and t.scenario.content_notes)
    ]
    return ethos


@router.get("/runs/{run_id}")
async def read_ethos_run(
    run_id: uuid.UUID, user: ReaderUser, db: Db, settings: AppSettings, label: str | None = None
) -> EthosRunOut:
    run = await _ethos_run(db, run_id)
    ethos = _visible(user, await load_run_ethos(db, run, order=_order(settings)))
    summary = await _summary(db, run, ethos)
    samples = (
        await db.execute(
            select(RunSample).where(RunSample.run_id == run.id).order_by(RunSample.sample_index)
        )
    ).scalars()
    kept = Counter(e.judge for t in ethos.transcripts for e in t.evidence)
    dropped = Counter(d.judge_model for d in ethos.dropped)
    evidence = [
        EthosEvidenceOut(
            id=uuid.UUID(e.id),
            transcript_id=t.transcript.id,
            message_id=uuid.UUID(e.message_id),
            label=e.label,
            judge=e.judge,
            intensity=e.intensity,
            quote=e.quote,
            channel=e.channel,
        )
        for t in ethos.transcripts
        for e in t.evidence
        if label is not None and e.label == label
    ]
    return EthosRunOut(
        **summary.model_dump(),
        judges=ethos.judges,
        samples=[SampleOut.model_validate(sample) for sample in samples],
        labels=label_shares(ethos.replies, ethos.labels),
        transcripts=[
            EthosTranscriptSummary(
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
            for t in ethos.transcripts
        ],
        judge_counts=[
            JudgeCountOut(judge=judge, kept=kept[judge], dropped=dropped[judge])
            for judge in ethos.judges
        ],
        dropped=_dropped(ethos),
        evidence=sorted(evidence, key=lambda e: -e.intensity),
    )


@router.get("/runs/{run_id}/transcripts/{transcript_id}")
async def read_ethos_transcript(
    run_id: uuid.UUID, transcript_id: uuid.UUID, user: ReaderUser, db: Db, settings: AppSettings
) -> EthosTranscriptOut:
    run = await _ethos_run(db, run_id)
    ethos = await load_run_ethos(db, run, only=[transcript_id], order=_order(settings))
    if not ethos.transcripts:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "This Ethos run did not read that transcript."
        )
    (found,) = ethos.transcripts
    _check_content_notes(user, found.scenario)
    families = {label.key: label.family for label in ethos.labels}
    index = {str(m.id): m.index for m in found.messages}
    taxonomy = {label.key: label for label in load_ethos(settings.repo_root).taxonomy.labels}
    return EthosTranscriptOut(
        run=RunOut.model_validate(run),
        source=RunOut.model_validate(await _source(db, run)),
        transcript_id=found.transcript.id,
        scenario_key=found.scenario.key if found.scenario else None,
        scenario_type=found.scenario.scenario_type if found.scenario else None,
        seed_text=found.scenario.seed_text if found.scenario else None,
        content_notes=found.scenario.content_notes if found.scenario else [],
        judges=ethos.judges,
        messages=[MessageOut.model_validate(m) for m in found.messages],
        replies=[
            ReplyEthosOut(
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
            EthosLabelOut(
                key=label.key,
                family=label.family,
                definition=" ".join(label.definition.split()),
                examples=list(taxonomy[label.key].examples) if label.key in taxonomy else [],
                counter_examples=list(taxonomy[label.key].counter_examples)
                if label.key in taxonomy
                else [],
                trust_status=label.trust_status,
            )
            for label in ethos.labels
        ],
        dropped=_dropped(ethos, {m.id for m in found.messages}),
    )


@router.get("/compare")
async def compare_ethos_runs(
    a: uuid.UUID, b: uuid.UUID, user: ReaderUser, db: Db, settings: AppSettings
) -> EthosCompareOut:
    """Prompt A beside prompt B, on the scenarios both runs read."""
    run_a, run_b = await _ethos_run(db, a), await _ethos_run(db, b)
    if run_a.taxonomy_version != run_b.taxonomy_version:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "These runs used different taxonomy versions."
        )
    order = _order(settings)
    ethos_a = _visible(user, await load_run_ethos(db, run_a, order=order))
    ethos_b = _visible(user, await load_run_ethos(db, run_b, order=order))

    def keyed(ethos: RunEthos) -> dict[str, list[ResponseView]]:
        grouped: dict[str, list[ResponseView]] = {}
        for t in ethos.transcripts:
            if t.scenario:
                grouped.setdefault(t.scenario.key, []).append(t)
        return grouped

    groups_a, groups_b = keyed(ethos_a), keyed(ethos_b)
    shared = sorted(set(groups_a) & set(groups_b))
    replies_a = [r for key in shared for t in groups_a[key] for r in t.replies]
    replies_b = [r for key in shared for t in groups_b[key] for r in t.replies]
    side_a = {p.label: p for p in label_shares(replies_a, ethos_a.labels)}
    side_b = {p.label: p for p in label_shares(replies_b, ethos_b.labels)}
    labels = []
    for label in ethos_a.labels:
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
    return EthosCompareOut(
        a=await _summary(db, run_a, ethos_a),
        b=await _summary(db, run_b, ethos_b),
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
async def stream_ethos_run(
    run_id: uuid.UUID, _: ReaderUser, db: Db
) -> AsyncIterator[ServerSentEvent]:
    await _ethos_run(db, run_id)
    async for event in status_events(run_id):
        yield event


@router.post("/runs/{run_id}/cancel")
async def cancel_ethos_run(run_id: uuid.UUID, user: AuthorUser, db: Db) -> RunOut:
    return await cancel_run(await _ethos_run(db, run_id), user, db)
