"""Load an Ethos run's findings and compute what its views show."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core.ethos.results import Evidence, ReplyEthos, reply_ethos
from agora_core.ethos.taxonomy import Expect
from agora_core.models import (
    Annotation,
    DroppedFinding,
    ExpectedProfile,
    Label,
    Message,
    Run,
    Scenario,
    TaxonomyVersion,
    Transcript,
)


@dataclass(frozen=True)
class LabelInfo:
    id: uuid.UUID
    key: str
    family: str
    definition: str
    trust_status: str


@dataclass
class ResponseView:
    transcript: Transcript
    scenario: Scenario | None
    messages: list[Message]
    replies: list[ReplyEthos]
    expected: dict[str, Expect] | None
    evidence: list[Evidence] = field(default_factory=list)

    @property
    def fit(self) -> float | None:
        scores = [r.fit.score for r in self.replies if r.fit and r.fit.score is not None]
        return sum(scores) / len(scores) if scores else None

    @property
    def disputed(self) -> int:
        return sum(len(reply.disputed) for reply in self.replies)


@dataclass
class RunEthos:
    run: Run
    judges: list[str]
    labels: list[LabelInfo]
    transcripts: list[ResponseView]
    dropped: list[DroppedFinding]

    @property
    def replies(self) -> list[ReplyEthos]:
        return [reply for t in self.transcripts for reply in t.replies]

    def label(self, key: str) -> LabelInfo | None:
        return next((label for label in self.labels if label.key == key), None)


async def taxonomy_labels(db: AsyncSession, version: str) -> tuple[uuid.UUID, list[LabelInfo]]:
    taxonomy = (
        await db.execute(select(TaxonomyVersion).where(TaxonomyVersion.version == version))
    ).scalar_one()
    rows = (
        await db.execute(select(Label).where(Label.taxonomy_version_id == taxonomy.id))
    ).scalars()
    labels = [
        LabelInfo(row.id, row.key, row.family, row.definition, row.trust_status) for row in rows
    ]
    return taxonomy.id, labels


async def expected_profiles(
    db: AsyncSession, taxonomy_id: uuid.UUID, keys: dict[uuid.UUID, str]
) -> dict[str, dict[str, Expect]]:
    profiles: dict[str, dict[str, Expect]] = defaultdict(dict)
    rows = (
        await db.execute(
            select(ExpectedProfile).where(ExpectedProfile.taxonomy_version_id == taxonomy_id)
        )
    ).scalars()
    for row in rows:
        profiles[row.scenario_type][keys[row.label_id]] = Expect(
            expect=row.expectation,
            min=row.intensity_min,
            max=row.intensity_max,
        )
    return dict(profiles)


def is_reply(message: Message) -> bool:
    """A reply Ethos reads: an agent message with words in it, not only a tool call."""
    return message.role == "assistant" and bool(message.content.strip())


async def load_run_ethos(
    db: AsyncSession,
    run: Run,
    only: list[uuid.UUID] | None = None,
    order: list[str] | None = None,
) -> RunEthos:
    """``order`` lists label keys in taxonomy order; labels follow it, then by key."""
    judges = list(run.config["panel"].values())
    taxonomy_id, labels = await taxonomy_labels(db, run.config["taxonomy_version"])
    rank = {key: i for i, key in enumerate(order or [])}
    labels.sort(key=lambda label: (rank.get(label.key, len(rank)), label.key))
    keys = {label.id: label.key for label in labels}
    profiles = await expected_profiles(db, taxonomy_id, keys)
    ids = [uuid.UUID(t) for t in run.config["transcripts"]]
    if only is not None:
        ids = [i for i in ids if i in set(only)]
    rows = (
        await db.execute(
            select(Transcript, Scenario)
            .outerjoin(Scenario, Scenario.id == Transcript.scenario_id)
            .where(Transcript.id.in_(ids))
        )
    ).all()
    by_id = {transcript.id: (transcript, scenario) for transcript, scenario in rows}
    messages: dict[uuid.UUID, list[Message]] = defaultdict(list)
    for message in (
        await db.execute(
            select(Message).where(Message.transcript_id.in_(ids)).order_by(Message.index)
        )
    ).scalars():
        messages[message.transcript_id].append(message)
    message_ids = [m.id for group in messages.values() for m in group]
    transcript_of = {m.id: m.transcript_id for group in messages.values() for m in group}
    evidence: dict[uuid.UUID, list[Evidence]] = defaultdict(list)
    if message_ids:
        for annotation in (
            await db.execute(
                select(Annotation).where(
                    Annotation.run_id == run.id, Annotation.message_id.in_(message_ids)
                )
            )
        ).scalars():
            evidence[transcript_of[annotation.message_id]].append(
                Evidence(
                    id=str(annotation.id),
                    message_id=str(annotation.message_id),
                    judge=annotation.judge_model,
                    label=keys[annotation.label_id],
                    intensity=annotation.intensity,
                    quote=annotation.quote,
                    start=annotation.char_start,
                    end=annotation.char_end,
                    channel=annotation.channel,
                    rationale=annotation.rationale,
                )
            )
    transcripts = []
    for transcript_id in ids:
        if transcript_id not in by_id:
            continue
        transcript, scenario = by_id[transcript_id]
        scenario_type = scenario.scenario_type if scenario else None
        expected = profiles.get(scenario_type) if scenario_type else None
        found = evidence[transcript_id]
        replies = [
            reply_ethos(str(m.id), judges, found, expected)
            for m in messages[transcript_id]
            if is_reply(m)
        ]
        transcripts.append(
            ResponseView(transcript, scenario, messages[transcript_id], replies, expected, found)
        )
    dropped = list(
        (await db.execute(select(DroppedFinding).where(DroppedFinding.run_id == run.id))).scalars()
    )
    return RunEthos(run, judges, labels, transcripts, dropped)
