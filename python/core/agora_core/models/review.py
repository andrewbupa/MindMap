"""Expert review, the gold set and agreement statistics."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from agora_core.models.base import Base, CreatedAt, UUIDPrimaryKey


class Review(UUIDPrimaryKey, CreatedAt, Base):
    """An expert's verdict on a score or an annotation. Reviews never edit what they judge."""

    __tablename__ = "review"
    __table_args__ = (
        CheckConstraint("(annotation_id IS NULL) <> (score_id IS NULL)", name="one_target"),
        CheckConstraint("verdict IN ('agree', 'disagree', 'unsure')", name="known_verdict"),
        CheckConstraint(
            "corrected_intensity IS NULL OR corrected_intensity BETWEEN 0 AND 3",
            name="intensity_range",
        ),
    )

    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    annotation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("annotation.id"))
    score_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("score.id"))
    verdict: Mapped[str] = mapped_column(String(10))
    corrected_intensity: Mapped[int | None] = mapped_column(SmallInteger)
    corrected_value: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")


class GoldSet(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "gold_set"

    name: Mapped[str] = mapped_column(String(200), unique=True)
    taxonomy_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("taxonomy_version.id"))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")


class GoldItem(UUIDPrimaryKey, Base):
    __tablename__ = "gold_item"
    __table_args__ = (UniqueConstraint("gold_set_id", "transcript_id"),)

    gold_set_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gold_set.id"))
    transcript_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transcript.id"))


class GoldLabel(UUIDPrimaryKey, CreatedAt, Base):
    """One expert's independent intensity for one label on one assistant message."""

    __tablename__ = "gold_label"
    __table_args__ = (
        UniqueConstraint("gold_item_id", "labeller_id", "message_id", "label_id"),
        CheckConstraint("intensity BETWEEN 0 AND 3", name="intensity_range"),
    )

    gold_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gold_item.id"))
    labeller_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("message.id"))
    label_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("label.id"))
    intensity: Mapped[int] = mapped_column(SmallInteger)
    quote: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")


class Agreement(UUIDPrimaryKey, Base):
    """Krippendorff's alpha for one label, between experts or between judges and experts."""

    __tablename__ = "agreement"
    __table_args__ = (
        CheckConstraint("comparison IN ('expert_expert', 'judge_expert')", name="known_comparison"),
    )

    gold_set_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gold_set.id"))
    label_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("label.id"))
    comparison: Mapped[str] = mapped_column(String(20))
    judge_model: Mapped[str | None] = mapped_column(String(200))
    alpha: Mapped[float | None] = mapped_column(Float)
    n_units: Mapped[int] = mapped_column(Integer)
    computed_at: Mapped[datetime]
