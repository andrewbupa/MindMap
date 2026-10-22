"""The gold set: experts label transcripts independently; Agora measures agreement.

Labelling is blind: an expert sees the conversation and the labels, never the
judges' findings or another expert's ratings. Admins create sets and compute
agreement, which updates each label's trust.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from agora_api.deps import AdminUser, AppSettings, Db, require_role
from agora_api.schemas import (
    AgreementOut,
    GoldItemDetail,
    GoldItemOut,
    GoldItemsAdd,
    GoldRatingOut,
    GoldRatingsIn,
    GoldSetCreate,
    GoldSetOut,
    GoldSetSummary,
    LensLabelOut,
    MessageOut,
)
from agora_core import gold
from agora_core.lens.read import is_reply
from agora_core.lens.taxonomy import load_lens
from agora_core.models import (
    GoldItem,
    GoldLabel,
    GoldSet,
    Label,
    Message,
    Role,
    Run,
    Scenario,
    TaxonomyVersion,
    Transcript,
    User,
)

router = APIRouter(prefix="/review/gold-sets", tags=["gold"])

ReviewerUser = Annotated[User, Depends(require_role(Role.reviewer))]


def _rank(settings: AppSettings) -> dict[str, int]:
    """Each label's place in the taxonomy, so lists follow it family by family."""
    return {label.key: i for i, label in enumerate(load_lens(settings.repo_root).taxonomy.labels)}


async def _gold_set(db: Db, set_id: uuid.UUID) -> GoldSet:
    found = await db.get(GoldSet, set_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such gold set.")
    return found


async def _summary(db: Db, gold_set: GoldSet, user: User) -> GoldSetSummary:
    version = await db.get(TaxonomyVersion, gold_set.taxonomy_version_id)
    items = list(
        (await db.execute(select(GoldItem).where(GoldItem.gold_set_id == gold_set.id))).scalars()
    )
    labellers = await gold.labellers_by_item(db, gold_set)
    return GoldSetSummary(
        id=gold_set.id,
        name=gold_set.name,
        description=gold_set.description,
        taxonomy_version=version.version if version else "",
        created_at=gold_set.created_at,
        items=len(items),
        fully_labelled=sum(
            1 for item in items if len(labellers.get(item.id, set())) >= gold.LABELLERS
        ),
        labelled_by_me=sum(1 for item in items if user.id in labellers.get(item.id, set())),
    )


@router.get("")
async def list_gold_sets(user: ReviewerUser, db: Db) -> list[GoldSetSummary]:
    sets = (await db.execute(select(GoldSet).order_by(GoldSet.created_at.desc()))).scalars()
    return [await _summary(db, gold_set, user) for gold_set in sets]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_gold_set(body: GoldSetCreate, user: AdminUser, db: Db) -> GoldSetSummary:
    source = await db.get(Run, body.source_run)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such run.")
    latest = (
        (await db.execute(select(TaxonomyVersion).order_by(TaxonomyVersion.created_at.desc())))
        .scalars()
        .first()
    )
    if latest is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No Lens taxonomy is loaded.")
    try:
        gold_set, _ = await gold.create_gold_set(
            db,
            name=body.name,
            description=body.description,
            taxonomy_version=latest.version,
            source=source,
            size=body.size,
            seed=body.seed,
            created_by=user.id,
        )
    except gold.GoldError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    await db.commit()
    return await _summary(db, gold_set, user)


@router.post("/{set_id}/items", status_code=status.HTTP_201_CREATED)
async def add_gold_items(
    set_id: uuid.UUID, body: GoldItemsAdd, user: AdminUser, db: Db
) -> GoldSetSummary:
    gold_set = await _gold_set(db, set_id)
    source = await db.get(Run, body.source_run)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such run.")
    try:
        await gold.add_items(db, gold_set, source, size=body.size, seed=body.seed)
    except gold.GoldError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    await db.commit()
    return await _summary(db, gold_set, user)


async def _agreement(db: Db, gold_set: GoldSet, rank: dict[str, int]) -> list[AgreementOut]:
    labels = {
        label.id: label
        for label in (
            await db.execute(
                select(Label).where(Label.taxonomy_version_id == gold_set.taxonomy_version_id)
            )
        ).scalars()
    }
    return [
        AgreementOut(
            label=labels[row.label_id].key,
            family=labels[row.label_id].family,
            comparison=row.comparison,
            judge_model=row.judge_model,
            alpha=row.alpha,
            n_units=row.n_units,
            computed_at=row.computed_at,
        )
        for row in sorted(
            await gold.latest_agreement(db, gold_set),
            key=lambda row: (rank.get(labels[row.label_id].key, len(rank)), row.judge_model or ""),
        )
    ]


@router.get("/{set_id}")
async def read_gold_set(
    set_id: uuid.UUID, user: ReviewerUser, db: Db, settings: AppSettings
) -> GoldSetOut:
    gold_set = await _gold_set(db, set_id)
    summary = await _summary(db, gold_set, user)
    labellers = await gold.labellers_by_item(db, gold_set)
    rows = (
        await db.execute(
            select(GoldItem, Scenario)
            .join(Transcript, Transcript.id == GoldItem.transcript_id)
            .outerjoin(Scenario, Scenario.id == Transcript.scenario_id)
            .where(GoldItem.gold_set_id == gold_set.id)
            .order_by(Scenario.key, GoldItem.id)
        )
    ).all()
    items, hidden = [], 0
    for item, scenario in rows:
        notes = scenario.content_notes if scenario else []
        if notes and not user.sensitive_opt_in:
            hidden += 1
            continue
        items.append(
            GoldItemOut(
                id=item.id,
                transcript_id=item.transcript_id,
                scenario_key=scenario.key if scenario else None,
                content_notes=notes,
                labellers=len(labellers.get(item.id, set())),
                labelled_by_me=user.id in labellers.get(item.id, set()),
            )
        )
    trust = {
        label.key: label.trust_status
        for label in (
            await db.execute(
                select(Label).where(Label.taxonomy_version_id == gold_set.taxonomy_version_id)
            )
        ).scalars()
    }
    return GoldSetOut(
        **summary.model_dump(),
        items_list=items,
        hidden_for_content_notes=hidden,
        agreement=await _agreement(db, gold_set, _rank(settings)),
        trust=trust,
    )


@router.post("/{set_id}/agreement")
async def compute_gold_agreement(
    set_id: uuid.UUID, user: AdminUser, db: Db, settings: AppSettings
) -> list[AgreementOut]:
    gold_set = await _gold_set(db, set_id)
    await gold.compute_agreement(db, gold_set, user.id)
    await db.commit()
    return await _agreement(db, gold_set, _rank(settings))


async def _item(
    db: Db, gold_set: GoldSet, item_id: uuid.UUID, user: User
) -> tuple[GoldItem, Scenario | None]:
    item = await db.get(GoldItem, item_id)
    if item is None or item.gold_set_id != gold_set.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such item in this gold set.")
    transcript = await db.get(Transcript, item.transcript_id)
    scenario = (
        await db.get(Scenario, transcript.scenario_id)
        if transcript and transcript.scenario_id
        else None
    )
    if scenario and scenario.content_notes and not user.sensitive_opt_in:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Opt in under Settings, preferences to label this item."
        )
    return item, scenario


@router.get("/{set_id}/items/{item_id}")
async def read_gold_item(
    set_id: uuid.UUID, item_id: uuid.UUID, user: ReviewerUser, db: Db, settings: AppSettings
) -> GoldItemDetail:
    gold_set = await _gold_set(db, set_id)
    item, scenario = await _item(db, gold_set, item_id, user)
    messages = list(
        (
            await db.execute(
                select(Message)
                .where(Message.transcript_id == item.transcript_id)
                .order_by(Message.index)
            )
        ).scalars()
    )
    labels = list(
        (
            await db.execute(
                select(Label).where(Label.taxonomy_version_id == gold_set.taxonomy_version_id)
            )
        ).scalars()
    )
    rank = _rank(settings)
    labels.sort(key=lambda label: (rank.get(label.key, len(rank)), label.key))
    keys = {label.id: label.key for label in labels}
    mine = (
        await db.execute(
            select(GoldLabel).where(
                GoldLabel.gold_item_id == item.id, GoldLabel.labeller_id == user.id
            )
        )
    ).scalars()
    labellers = await gold.labellers_by_item(db, gold_set)
    order = list(
        (
            await db.execute(
                select(GoldItem.id).where(GoldItem.gold_set_id == gold_set.id).order_by(GoldItem.id)
            )
        ).scalars()
    )
    waiting = [i for i in order if i != item.id and user.id not in labellers.get(i, set())]
    return GoldItemDetail(
        id=item.id,
        gold_set=gold_set.id,
        gold_set_name=gold_set.name,
        transcript_id=item.transcript_id,
        scenario_key=scenario.key if scenario else None,
        seed_text=scenario.seed_text if scenario else None,
        content_notes=scenario.content_notes if scenario else [],
        messages=[MessageOut.model_validate(m) for m in messages],
        replies=[m.id for m in messages if is_reply(m)],
        labels=[
            LensLabelOut(
                key=label.key,
                family=label.family,
                definition=" ".join(label.definition.split()),
                examples=[str(e) for e in label.examples],
                counter_examples=[str(e) for e in label.counter_examples],
                trust_status=label.trust_status,
            )
            for label in labels
        ],
        mine=[
            GoldRatingOut(
                message_id=row.message_id,
                label=keys[row.label_id],
                intensity=row.intensity,
                quote=row.quote,
            )
            for row in mine
        ],
        next_item=waiting[0] if waiting else None,
    )


@router.put("/{set_id}/items/{item_id}/ratings")
async def save_gold_ratings(
    set_id: uuid.UUID, item_id: uuid.UUID, body: GoldRatingsIn, user: ReviewerUser, db: Db
) -> list[GoldRatingOut]:
    gold_set = await _gold_set(db, set_id)
    item, _ = await _item(db, gold_set, item_id, user)
    try:
        await gold.save_ratings(
            db,
            item=item,
            labeller=user.id,
            ratings=[gold.Rating(r.message_id, r.label, r.intensity) for r in body.ratings],
            quotes={(r.message_id, r.label): r.quote for r in body.ratings if r.quote},
        )
    except gold.GoldError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    await db.commit()
    return [
        GoldRatingOut(message_id=r.message_id, label=r.label, intensity=r.intensity, quote=r.quote)
        for r in body.ratings
    ]
