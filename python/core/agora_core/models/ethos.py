"""Ethos: the taxonomy of dispositions, expected profiles and phrase-level findings."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from agora_core.models.base import Base, CreatedAt, UUIDPrimaryKey


class TrustStatus(StrEnum):
    unrated = "unrated"
    provisional = "provisional"
    trusted = "trusted"
    retired = "retired"


class Expectation(StrEnum):
    present = "present"
    absent = "absent"
    either = "either"


class TaxonomyVersion(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "taxonomy_version"

    version: Mapped[str] = mapped_column(String(50), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    git_commit: Mapped[str] = mapped_column(String(64))


class Label(UUIDPrimaryKey, Base):
    __tablename__ = "label"
    __table_args__ = (
        UniqueConstraint("taxonomy_version_id", "key"),
        CheckConstraint(
            "trust_status IN ('unrated', 'provisional', 'trusted', 'retired')",
            name="known_trust_status",
        ),
    )

    taxonomy_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("taxonomy_version.id"))
    key: Mapped[str] = mapped_column(String(100))
    family: Mapped[str] = mapped_column(String(50))
    definition: Mapped[str] = mapped_column(Text)
    examples: Mapped[list[Any]]
    counter_examples: Mapped[list[Any]]
    source: Mapped[str] = mapped_column(String(300))
    trust_status: Mapped[str] = mapped_column(
        String(20), default=TrustStatus.unrated.value, server_default="unrated"
    )


class ExpectedProfile(UUIDPrimaryKey, Base):
    __tablename__ = "expected_profile"
    __table_args__ = (
        UniqueConstraint("taxonomy_version_id", "scenario_type", "label_id"),
        CheckConstraint("expectation IN ('present', 'absent', 'either')", name="known_expectation"),
        CheckConstraint(
            "intensity_min BETWEEN 0 AND 3 AND intensity_max BETWEEN 0 AND 3"
            " AND intensity_min <= intensity_max",
            name="intensity_band",
        ),
    )

    taxonomy_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("taxonomy_version.id"))
    scenario_type: Mapped[str] = mapped_column(String(100))
    label_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("label.id"))
    expectation: Mapped[str] = mapped_column(String(10))
    intensity_min: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    intensity_max: Mapped[int] = mapped_column(SmallInteger, default=3, server_default="3")


class Annotation(UUIDPrimaryKey, CreatedAt, Base):
    """One judge's finding: an exact quote from a message, verified in code."""

    __tablename__ = "annotation"
    __table_args__ = (
        CheckConstraint("intensity BETWEEN 0 AND 3", name="intensity_range"),
        CheckConstraint("char_start >= 0 AND char_end > char_start", name="offsets"),
        Index(None, "message_id", "label_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id"))
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("message.id"))
    label_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("label.id"))
    judge_model: Mapped[str] = mapped_column(String(200))
    quote: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    intensity: Mapped[int] = mapped_column(SmallInteger)
    rationale: Mapped[str] = mapped_column(Text)
    # Which text the finding quotes: the visible answer or the thinking summary.
    channel: Mapped[str] = mapped_column(String(20), default="content", server_default="content")


class DroppedFinding(UUIDPrimaryKey, CreatedAt, Base):
    """A finding whose quote was not found in its message. Counted against the judge."""

    __tablename__ = "dropped_finding"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("message.id"))
    judge_model: Mapped[str] = mapped_column(String(200))
    label_key: Mapped[str] = mapped_column(String(100))
    quote: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(String(50))
