"""The Ethos job: one transcript, read by the whole panel. See agora_core.ethos.runs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from inspect_ai.model import Model
from procrastinate import RetryStrategy
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core.db import session_scope
from agora_core.ethos.findings import Reply, check
from agora_core.ethos.quotes import DropReason
from agora_core.models import Annotation, DroppedFinding, Label, Message, TaxonomyVersion
from agora_core.queue import RUNS_QUEUE, app
from agora_core.storage import Storage, get_storage, object_key
from agora_worker.ethos.judging import PanelReading, judged_messages, read_with_panel
from agora_worker.ethos.scanners import LabelText
from agora_worker.inquiry.runner import ModelFactory, default_models
from agora_worker.samples import MAX_ATTEMPTS, Claim, SampleChanged, execute

RETRY = RetryStrategy(max_attempts=MAX_ATTEMPTS, wait=30, retry_exceptions={RuntimeError})


@app.task(name="ethos_sample", queue=RUNS_QUEUE, retry=RETRY)
async def ethos_sample(run_sample_id: str) -> None:
    await execute_ethos_sample(uuid.UUID(run_sample_id))


def raw_key(run_id: uuid.UUID, index: int) -> str:
    return object_key("runs", str(run_id), "samples", f"{index:04d}-judges.json")


@dataclass
class EthosWork:
    claim: Claim
    rows: list[Message]
    labels: list[LabelText]
    label_ids: dict[str, uuid.UUID]
    judges: dict[str, Model]
    storage: Storage

    async def run(self) -> PanelReading:
        reading = await read_with_panel(
            judged_messages(self.rows), self.labels, self.claim.config["families"], self.judges
        )
        # What every judge said, before any checking, kept as evidence beside the findings.
        key = raw_key(self.claim.run_id, self.claim.index)
        await self.storage.aput_bytes(key, reading.raw_json(), "application/json")
        reading.log_uri = f"s3://{self.storage.bucket}/{key}"
        return reading

    async def record(self, db: AsyncSession, outcome: PanelReading) -> None:
        replies = {
            str(row.id): Reply(str(row.id), row.role, row.content, row.thinking_summary)
            for row in self.rows
        }
        families: dict[str, set[str]] = {}
        for label in self.labels:
            families.setdefault(label.family, set()).add(label.key)
        kept, dropped = check(outcome.findings, replies, families)
        run_id = self.claim.run_id
        for item in kept:
            db.add(
                Annotation(
                    run_id=run_id,
                    message_id=uuid.UUID(item.finding.message_id or ""),
                    label_id=self.label_ids[item.finding.label],
                    judge_model=item.finding.judge,
                    quote=item.finding.quote,
                    char_start=item.span.start,
                    char_end=item.span.end,
                    intensity=item.finding.intensity,
                    rationale=item.finding.rationale,
                    channel=item.channel.value,
                )
            )
        for miss in dropped:
            known = miss.finding.message_id in replies
            db.add(
                DroppedFinding(
                    run_id=run_id,
                    message_id=uuid.UUID(miss.finding.message_id or "") if known else None,
                    judge_model=miss.finding.judge,
                    label_key=miss.finding.label,
                    quote=miss.finding.quote,
                    reason=miss.reason.value,
                )
            )
        for judge, family in outcome.unanswered:
            db.add(
                DroppedFinding(
                    run_id=run_id,
                    message_id=None,
                    judge_model=judge,
                    label_key=family,
                    quote="",
                    reason=DropReason.no_answer.value,
                )
            )
        await db.flush()


async def execute_ethos_sample(
    sample_id: uuid.UUID,
    *,
    models: ModelFactory = default_models,
    storage: Storage | None = None,
) -> None:
    async def plan(claim: Claim) -> EthosWork:
        config = claim.config
        transcript_id = uuid.UUID(config["transcripts"][claim.index])
        async with session_scope() as db:
            taxonomy = (
                await db.execute(
                    select(TaxonomyVersion).where(
                        TaxonomyVersion.version == config["taxonomy_version"]
                    )
                )
            ).scalar_one_or_none()
            if taxonomy is None or taxonomy.sha256 != config["taxonomy_sha"]:
                raise SampleChanged("the run's taxonomy version is missing or changed")
            stored = list(
                (
                    await db.execute(select(Label).where(Label.taxonomy_version_id == taxonomy.id))
                ).scalars()
            )
            rows = list(
                (
                    await db.execute(
                        select(Message)
                        .where(Message.transcript_id == transcript_id)
                        .order_by(Message.index)
                    )
                ).scalars()
            )
        if not rows:
            raise SampleChanged("the transcript has no messages")
        # The judge reads the labels as the run's taxonomy version stored them.
        labels = [
            LabelText(
                key=label.key,
                family=label.family,
                definition=" ".join(label.definition.split()),
                examples=[str(e) for e in label.examples],
                counter_examples=[str(e) for e in label.counter_examples],
            )
            for label in stored
        ]
        judges = {
            model_id: models(role, model_id, config["generate"].get(role, {}))
            for role, model_id in config["panel"].items()
        }
        return EthosWork(
            claim=claim,
            rows=rows,
            labels=labels,
            label_ids={label.key: label.id for label in stored},
            judges=judges,
            storage=storage or get_storage(),
        )

    await execute(sample_id, plan)
