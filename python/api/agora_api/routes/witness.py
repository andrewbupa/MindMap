"""The open-model witness: launch readings of finished runs on the Droplet runner,
read the signals, and set them beside Ethos labels. See agora_core.witness."""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy import select

from agora_api.deps import AppSettings, AuthorUser, Db, ReaderUser
from agora_api.routes.ethos import _order, _visible
from agora_api.routes.inquiry import _check_content_notes
from agora_api.run_control import cancel_run, status_events
from agora_api.schemas import (
    ReplyRefOut,
    RunOut,
    SignalAgreementOut,
    TokenValueOut,
    WitnessLaunch,
    WitnessReaderOut,
    WitnessRunOut,
    WitnessRunSummary,
    WitnessSampleOut,
    WitnessSignalOut,
    WitnessSignalSpecOut,
    WitnessTranscriptOut,
)
from agora_core import inquiry, queue
from agora_core.ethos.fit import PRESENT_AT
from agora_core.ethos.read import load_run_ethos
from agora_core.ethos.taxonomy import TaxonomyError
from agora_core.models import (
    FINISHED_STATUSES,
    Message,
    Run,
    RunKind,
    RunSample,
    RunStatus,
    Scenario,
    Transcript,
    User,
    WitnessSignal,
)
from agora_core.provenance import ProvenanceError, current_git_commit
from agora_core.witness import (
    ReaderConfig,
    WitnessConfig,
    WitnessError,
    compare,
    create_witness_run,
    get_witness,
)

router = APIRouter(prefix="/witness", tags=["witness"])
Witness = Annotated[WitnessConfig, Depends(get_witness)]


def _reader_out(key: str, reader: ReaderConfig) -> WitnessReaderOut:
    return WitnessReaderOut(
        key=key,
        model=reader.model,
        runner=reader.runner,
        version=reader.version,
        signals=[
            WitnessSignalSpecOut(
                name=s.name,
                kind=s.kind,
                description=s.description,
                label=s.label,
                present_at=s.present_at,
            )
            for s in reader.signals
        ],
    )


def _recorded_reader(run: Run) -> WitnessReaderOut:
    """The reader as the run recorded it, which may differ from today's config."""
    return _reader_out(
        run.config["reader"], ReaderConfig.model_validate(run.config["reader_config"])
    )


@router.get("/readers")
async def list_readers(_: ReaderUser, witness: Witness) -> list[WitnessReaderOut]:
    return [_reader_out(key, reader) for key, reader in witness.readers.items()]


@router.post("/runs", status_code=status.HTTP_201_CREATED)
async def launch_witness(
    body: WitnessLaunch, user: AuthorUser, db: Db, settings: AppSettings, witness: Witness
) -> RunOut:
    source = await db.get(Run, body.source_run)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such run.")
    try:
        run, samples = await create_witness_run(
            db,
            root=settings.repo_root,
            source=source,
            witness=witness,
            reader_key=body.reader,
            git_commit=current_git_commit(settings.repo_root, settings.git_commit),
            launched_by=user.id,
            transcript_ids=body.transcripts,
        )
    except (WitnessError, TaxonomyError, ProvenanceError) as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    await db.commit()
    # The Droplet runner takes this queue; App Platform's worker never does.
    for sample in samples:
        sample.job_id = await queue.defer(
            "witness_sample", queue=queue.WITNESS_QUEUE, run_sample_id=str(sample.id)
        )
    await db.commit()
    return RunOut.model_validate(run)


async def _witness_run(db: Db, run_id: uuid.UUID) -> Run:
    run = await db.get(Run, run_id)
    if run is None or run.kind != RunKind.witness.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such witness run.")
    return run


async def _summary(db: Db, run: Run) -> WitnessRunSummary:
    source = await db.get(Run, run.source_run_id) if run.source_run_id else None
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The witness run's source is missing.")
    return WitnessRunSummary(
        run=RunOut.model_validate(run),
        source=RunOut.model_validate(source),
        reader=_recorded_reader(run),
        counts=await inquiry.sample_counts(db, run.id),
    )


@router.get("/runs")
async def list_witness_runs(
    _: ReaderUser, db: Db, source_run: uuid.UUID | None = None
) -> list[WitnessRunSummary]:
    query = select(Run).where(Run.kind == RunKind.witness.value)
    if source_run is not None:
        query = query.where(Run.source_run_id == source_run)
    runs = (await db.execute(query.order_by(Run.created_at.desc()).limit(50))).scalars()
    return [await _summary(db, run) for run in runs]


async def _ethos_runs(db: Db, source_run_id: uuid.UUID | None) -> list[Run]:
    return list(
        (
            await db.execute(
                select(Run)
                .where(Run.kind == RunKind.ethos.value, Run.source_run_id == source_run_id)
                .where(Run.status.in_([s.value for s in FINISHED_STATUSES]))
                .order_by(Run.created_at.desc())
            )
        ).scalars()
    )


@router.get("/runs/{run_id}")
async def read_witness_run(
    run_id: uuid.UUID,
    user: ReaderUser,
    db: Db,
    settings: AppSettings,
    ethos_run: uuid.UUID | None = None,
) -> WitnessRunOut:
    """The run, and its signals beside an Ethos run on the same source: the one asked
    for, or the latest finished one."""
    run = await _witness_run(db, run_id)
    summary = await _summary(db, run)
    samples = list(
        (
            await db.execute(
                select(RunSample).where(RunSample.run_id == run.id).order_by(RunSample.sample_index)
            )
        ).scalars()
    )
    dropped: Counter[str] = Counter()
    for sample in samples:
        dropped.update(sample.detail.get("dropped", {}))
    choices = await _ethos_runs(db, run.source_run_id)
    chosen = next((r for r in choices if r.id == ethos_run), None) if ethos_run else None
    if ethos_run is not None and chosen is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No finished Ethos run on this source run has that ID."
        )
    chosen = chosen or (choices[0] if choices else None)
    agreements: list[SignalAgreementOut] = []
    if chosen is not None:
        agreements = await _agreements(db, run, samples, chosen, user, settings)
    return WitnessRunOut(
        **summary.model_dump(),
        samples=[
            WitnessSampleOut.model_validate(sample, from_attributes=True) for sample in samples
        ],
        dropped=dict(sorted(dropped.items())),
        ethos_run=RunOut.model_validate(chosen) if chosen else None,
        ethos_runs=[RunOut.model_validate(r) for r in choices],
        agreements=agreements,
    )


async def _agreements(
    db: Db,
    run: Run,
    samples: list[RunSample],
    ethos_run: Run,
    user: User,
    settings: AppSettings,
) -> list[SignalAgreementOut]:
    """Over the replies of transcripts both runs read in full and the reader may open."""
    read = [
        uuid.UUID(run.config["transcripts"][s.sample_index])
        for s in samples
        if s.status == RunStatus.succeeded.value
    ]
    ethos = _visible(user, await load_run_ethos(db, ethos_run, only=read, order=_order(settings)))
    medians: dict[str, dict[str, float]] = {}
    where: dict[str, ReplyRefOut] = {}
    index = {
        message_id: (transcript_id, position)
        for message_id, transcript_id, position in (
            await db.execute(
                select(Message.id, Message.transcript_id, Message.index).where(
                    Message.transcript_id.in_([t.transcript.id for t in ethos.transcripts])
                )
            )
        ).all()
    }
    for transcript in ethos.transcripts:
        for reply in transcript.replies:
            medians[reply.message_id] = {k: c.median for k, c in reply.labels.items()}
            transcript_id, position = index[uuid.UUID(reply.message_id)]
            where[reply.message_id] = ReplyRefOut(
                message_id=uuid.UUID(reply.message_id),
                transcript_id=transcript_id,
                index=position,
                scenario_key=transcript.scenario.key if transcript.scenario else None,
                epoch=transcript.transcript.epoch,
            )
    peaks: dict[str, dict[str, float]] = {}
    if where:
        for message_id, name, values in (
            await db.execute(
                select(WitnessSignal.message_id, WitnessSignal.name, WitnessSignal.values)
                .where(WitnessSignal.run_id == run.id)
                .where(WitnessSignal.message_id.in_([r.message_id for r in where.values()]))
            )
        ).all():
            by_name = peaks.setdefault(str(message_id), {})
            by_name[name] = max([by_name.get(name, float("-inf")), *values])
    reader = ReaderConfig.model_validate(run.config["reader_config"])
    labels = {label.key: label for label in ethos.labels}
    return [
        SignalAgreementOut(
            signal=a.signal,
            kind=a.kind,
            label=a.label,
            family=labels[a.label].family if a.label in labels else "",
            trust_status=labels[a.label].trust_status if a.label in labels else None,
            present_at=a.present_at,
            replies=a.replies,
            agreement=a.agreement,
            positive=a.positive,
            both=[where[m] for m in a.both],
            ethos_only=[where[m] for m in a.ethos_only],
            witness_only=[where[m] for m in a.witness_only],
            neither=[where[m] for m in a.neither],
        )
        for a in compare(list(where), medians, peaks, reader.signals, PRESENT_AT)
    ]


@router.get("/runs/{run_id}/transcripts/{transcript_id}")
async def read_witness_transcript(
    run_id: uuid.UUID, transcript_id: uuid.UUID, user: ReaderUser, db: Db
) -> WitnessTranscriptOut:
    run = await _witness_run(db, run_id)
    if str(transcript_id) not in run.config["transcripts"]:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "This witness run did not read that transcript."
        )
    row = (
        await db.execute(
            select(Transcript, Scenario)
            .outerjoin(Scenario, Scenario.id == Transcript.scenario_id)
            .where(Transcript.id == transcript_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such transcript.")
    _check_content_notes(user, row[1])
    reader = ReaderConfig.model_validate(run.config["reader_config"])
    specs = {spec.name: spec for spec in reader.signals}
    signals = (
        await db.execute(
            select(WitnessSignal)
            .join(Message, Message.id == WitnessSignal.message_id)
            .where(WitnessSignal.run_id == run.id, Message.transcript_id == transcript_id)
            .order_by(Message.index, WitnessSignal.name, WitnessSignal.char_start)
        )
    ).scalars()
    return WitnessTranscriptOut(
        run=RunOut.model_validate(run),
        reader=_recorded_reader(run),
        signals=[
            WitnessSignalOut(
                id=signal.id,
                message_id=signal.message_id,
                name=signal.name,
                kind=signal.kind,
                label=specs[signal.name].label if signal.name in specs else None,
                present_at=specs[signal.name].present_at if signal.name in specs else None,
                char_start=signal.char_start,
                char_end=signal.char_end,
                tokens=[
                    TokenValueOut(start=start, end=end, value=value)
                    for (start, end), value in zip(signal.offsets, signal.values, strict=True)
                ],
                peak=max(signal.values),
                explanation=signal.explanation,
            )
            for signal in signals
        ],
    )


@router.get("/runs/{run_id}/events", response_class=EventSourceResponse)
async def stream_witness_run(
    run_id: uuid.UUID, _: ReaderUser, db: Db
) -> AsyncIterator[ServerSentEvent]:
    await _witness_run(db, run_id)
    async for event in status_events(run_id):
        yield event


@router.post("/runs/{run_id}/cancel")
async def cancel_witness_run(run_id: uuid.UUID, user: AuthorUser, db: Db) -> RunOut:
    return await cancel_run(await _witness_run(db, run_id), user, db)
