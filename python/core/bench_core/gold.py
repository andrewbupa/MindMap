"""The gold set: transcripts labelled independently by experts, to calibrate Lens.

Items are drawn from finished runs by a seeded, repeatable sample. Each expert rates
every label on every reply of an item, from 0 (absent) to 3 (dominant), without
seeing the judges' findings or the other experts' ratings. Agreement is
Krippendorff's alpha per label (ordinal): between the experts, and between each Lens
judge and the experts' median. The experts' alpha sets each label's trust.
"""

from __future__ import annotations

import hashlib
import statistics
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bench_core import audit
from bench_core.agreement import alpha, pairable_values, trust
from bench_core.lens.runs import READABLE
from bench_core.models import (
    FINISHED_STATUSES,
    Agreement,
    Annotation,
    GoldItem,
    GoldLabel,
    GoldSet,
    Label,
    Message,
    Run,
    RunKind,
    RunStatus,
    TaxonomyVersion,
    Transcript,
)

GOLD_SIZE = 60
LABELLERS = 2
EXPERTS = "experts"


class GoldError(ValueError):
    pass


def sample(ids: list[uuid.UUID], size: int, seed: int) -> list[uuid.UUID]:
    """A repeatable sample: the same ids, size and seed always give the same items."""
    ranked = sorted(ids, key=lambda i: hashlib.sha256(f"{seed}:{i}".encode()).hexdigest())
    return ranked[:size]


async def add_items(
    db: AsyncSession, gold_set: GoldSet, source: Run, *, size: int, seed: int
) -> list[GoldItem]:
    if source.kind not in READABLE:
        raise GoldError("Gold items come from Explore, Measure or playground runs.")
    if source.status not in {s.value for s in FINISHED_STATUSES}:
        raise GoldError("Gold items come from finished runs only.")
    existing = set(
        (
            await db.execute(
                select(GoldItem.transcript_id).where(GoldItem.gold_set_id == gold_set.id)
            )
        ).scalars()
    )
    candidates = [
        t
        for t in (
            await db.execute(select(Transcript.id).where(Transcript.run_id == source.id))
        ).scalars()
        if t not in existing
    ]
    if not candidates:
        raise GoldError("That run has no transcripts the gold set does not already hold.")
    items = [
        GoldItem(gold_set_id=gold_set.id, transcript_id=t) for t in sample(candidates, size, seed)
    ]
    db.add_all(items)
    await db.flush()
    return items


async def create_gold_set(
    db: AsyncSession,
    *,
    name: str,
    description: str,
    taxonomy_version: str,
    source: Run,
    size: int,
    seed: int,
    created_by: uuid.UUID,
) -> tuple[GoldSet, list[GoldItem]]:
    taxonomy = (
        await db.execute(select(TaxonomyVersion).where(TaxonomyVersion.version == taxonomy_version))
    ).scalar_one_or_none()
    if taxonomy is None:
        raise GoldError(f"Taxonomy {taxonomy_version} is not loaded.")
    taken = (await db.execute(select(GoldSet.id).where(GoldSet.name == name))).first()
    if taken:
        raise GoldError("A gold set with that name already exists.")
    gold_set = GoldSet(name=name, description=description, taxonomy_version_id=taxonomy.id)
    db.add(gold_set)
    await db.flush()
    items = await add_items(db, gold_set, source, size=size, seed=seed)
    await audit.record(
        db,
        "gold.create",
        actor_id=created_by,
        target_type="gold_set",
        target_id=gold_set.id,
        detail={"source_run": str(source.id), "items": len(items), "seed": seed},
    )
    return gold_set, items


@dataclass(frozen=True)
class Rating:
    message_id: uuid.UUID
    label: str
    intensity: int


async def save_ratings(
    db: AsyncSession,
    *,
    item: GoldItem,
    labeller: uuid.UUID,
    ratings: list[Rating],
    quotes: dict[tuple[uuid.UUID, str], str] | None = None,
) -> int:
    """Replace one expert's ratings for one item. Only the agent's replies are rated."""
    gold_set = await db.get(GoldSet, item.gold_set_id)
    assert gold_set is not None
    labels = {
        label.key: label.id
        for label in (
            await db.execute(
                select(Label).where(Label.taxonomy_version_id == gold_set.taxonomy_version_id)
            )
        ).scalars()
    }
    replies = {
        message.id
        for message in (
            await db.execute(select(Message).where(Message.transcript_id == item.transcript_id))
        ).scalars()
        if message.role == "assistant" and message.content.strip()
    }
    for rating in ratings:
        if rating.message_id not in replies:
            raise GoldError("Rate only the agent's replies in this transcript.")
        if rating.label not in labels:
            raise GoldError(f"No label {rating.label} in this gold set's taxonomy.")
        if not 0 <= rating.intensity <= 3:
            raise GoldError("Intensity runs from 0 to 3.")
    old = (
        await db.execute(
            select(GoldLabel).where(
                GoldLabel.gold_item_id == item.id, GoldLabel.labeller_id == labeller
            )
        )
    ).scalars()
    for row in old:
        await db.delete(row)
    await db.flush()
    for rating in ratings:
        db.add(
            GoldLabel(
                gold_item_id=item.id,
                labeller_id=labeller,
                message_id=rating.message_id,
                label_id=labels[rating.label],
                intensity=rating.intensity,
                quote=(quotes or {}).get((rating.message_id, rating.label)),
            )
        )
    await db.flush()
    return len(ratings)


async def labellers_by_item(db: AsyncSession, gold_set: GoldSet) -> dict[uuid.UUID, set[uuid.UUID]]:
    rows = await db.execute(
        select(GoldLabel.gold_item_id, GoldLabel.labeller_id)
        .join(GoldItem, GoldItem.id == GoldLabel.gold_item_id)
        .where(GoldItem.gold_set_id == gold_set.id)
        .group_by(GoldLabel.gold_item_id, GoldLabel.labeller_id)
    )
    result: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for item_id, labeller in rows.all():
        result[item_id].add(labeller)
    return result


async def _judge_values(
    db: AsyncSession, gold_set: GoldSet, version: str, keys: dict[uuid.UUID, str]
) -> dict[str, dict[tuple[uuid.UUID, str], int]]:
    """For each Lens judge: its highest intensity per reply and label, 0 where it found
    nothing, from the newest finished Lens run that read each gold transcript."""
    transcripts = set(
        (
            await db.execute(
                select(GoldItem.transcript_id).where(GoldItem.gold_set_id == gold_set.id)
            )
        ).scalars()
    )
    runs = (
        await db.execute(
            select(Run)
            .where(Run.kind == RunKind.lens.value)
            .where(Run.status == RunStatus.succeeded.value)
            .where(Run.taxonomy_version == version)
            .order_by(Run.created_at.desc())
        )
    ).scalars()
    reader: dict[uuid.UUID, Run] = {}
    for run in runs:
        for t in run.config.get("transcripts", []):
            if uuid.UUID(t) in transcripts:
                reader.setdefault(uuid.UUID(t), run)
    values: dict[str, dict[tuple[uuid.UUID, str], int]] = defaultdict(dict)
    for transcript_id, run in reader.items():
        replies = [
            m.id
            for m in (
                await db.execute(select(Message).where(Message.transcript_id == transcript_id))
            ).scalars()
            if m.role == "assistant" and m.content.strip()
        ]
        for judge in run.config["panel"].values():
            for message_id in replies:
                for key in keys.values():
                    values[judge][(message_id, key)] = 0
        for annotation in (
            await db.execute(
                select(Annotation).where(
                    Annotation.run_id == run.id,
                    Annotation.message_id.in_(replies),
                    Annotation.channel == "content",
                )
            )
        ).scalars():
            unit = (annotation.message_id, keys[annotation.label_id])
            judge_values = values[annotation.judge_model]
            judge_values[unit] = max(judge_values.get(unit, 0), annotation.intensity)
    return values


async def compute_agreement(
    db: AsyncSession, gold_set: GoldSet, actor: uuid.UUID
) -> list[Agreement]:
    """Alpha per label between experts, and between each judge and the experts' median.
    Every computation is kept; the experts' alpha sets each label's trust."""
    version = await db.get(TaxonomyVersion, gold_set.taxonomy_version_id)
    assert version is not None
    labels = list(
        (await db.execute(select(Label).where(Label.taxonomy_version_id == version.id))).scalars()
    )
    keys = {label.id: label.key for label in labels}
    ratings = (
        await db.execute(
            select(GoldLabel)
            .join(GoldItem, GoldItem.id == GoldLabel.gold_item_id)
            .where(GoldItem.gold_set_id == gold_set.id)
        )
    ).scalars()
    experts: dict[str, dict[uuid.UUID, dict[uuid.UUID, float | None]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for row in ratings:
        experts[keys[row.label_id]][row.message_id][row.labeller_id] = float(row.intensity)
    judges = await _judge_values(db, gold_set, version.version, keys)
    now = datetime.now(UTC)
    computed: list[Agreement] = []
    for label in labels:
        units = experts.get(label.key, {})
        value = alpha(units)
        pairable = pairable_values(units)
        computed.append(
            Agreement(
                gold_set_id=gold_set.id,
                label_id=label.id,
                comparison="expert_expert",
                judge_model=None,
                alpha=value,
                n_units=sum(1 for coders in units.values() if len(coders) >= 2),
                computed_at=now,
            )
        )
        label.trust_status = trust(value, pairable).value
        for judge, judged in judges.items():
            paired: dict[uuid.UUID, dict[str, float | None]] = {}
            for message_id, coders in units.items():
                if (message_id, label.key) in judged and coders:
                    paired[message_id] = {
                        EXPERTS: statistics.median(v for v in coders.values() if v is not None),
                        judge: float(judged[(message_id, label.key)]),
                    }
            computed.append(
                Agreement(
                    gold_set_id=gold_set.id,
                    label_id=label.id,
                    comparison="judge_expert",
                    judge_model=judge,
                    alpha=alpha(paired),
                    n_units=len(paired),
                    computed_at=now,
                )
            )
    db.add_all(computed)
    await db.flush()
    await audit.record(
        db,
        "gold.agreement",
        actor_id=actor,
        target_type="gold_set",
        target_id=gold_set.id,
        detail={"labels": len(labels), "judges": sorted(judges)},
    )
    return computed


async def latest_agreement(db: AsyncSession, gold_set: GoldSet) -> list[Agreement]:
    newest = (
        await db.execute(
            select(func.max(Agreement.computed_at)).where(Agreement.gold_set_id == gold_set.id)
        )
    ).scalar_one_or_none()
    if newest is None:
        return []
    return list(
        (
            await db.execute(
                select(Agreement).where(
                    Agreement.gold_set_id == gold_set.id, Agreement.computed_at == newest
                )
            )
        ).scalars()
    )
