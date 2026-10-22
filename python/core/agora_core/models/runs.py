"""Runs and what they produce. A finished run, and everything under it, is read-only.

Triggers created in the initial migration enforce this in Postgres, so no code
path (and no hand-written SQL) can edit a finished run.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from agora_core.models.base import Base, CreatedAt, UUIDPrimaryKey


class RunKind(StrEnum):
    inquiry = "inquiry"
    tally = "tally"
    ethos = "ethos"
    rehearsal = "rehearsal"
    # Bloom's understanding and ideation for one behaviour version.
    scenarios = "scenarios"
    # An open-weight model's per-token signals on a finished run (agora_core.witness).
    witness = "witness"


class RunStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"
    stopped_at_budget = "stopped_at_budget"


FINISHED_STATUSES = (
    RunStatus.succeeded,
    RunStatus.failed,
    RunStatus.cancelled,
    RunStatus.stopped_at_budget,
)


def _values(enum: type[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in enum)


class Run(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "run"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_values(RunKind)})", name="known_kind"),
        CheckConstraint(f"status IN ({_values(RunStatus)})", name="known_status"),
        CheckConstraint("token_budget > 0", name="positive_budget"),
        Index(None, "kind", "created_at"),
    )

    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(
        String(20), default=RunStatus.queued.value, server_default=RunStatus.queued.value
    )
    title: Mapped[str] = mapped_column(String(300), default="", server_default="")

    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent.id"))
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("prompt_version.id"))
    tool_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tool_profile.id"))
    scenario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scenario.id"))
    behaviour_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("behaviour.id"))
    # An Ethos run reads transcripts produced by another run.
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run.id"))

    # Provenance: enough to reproduce the run months later.
    config: Mapped[dict[str, Any]]
    config_hash: Mapped[str] = mapped_column(String(64))
    git_commit: Mapped[str] = mapped_column(String(64))
    prompt_sha: Mapped[str | None] = mapped_column(String(64))
    seed_hash: Mapped[str | None] = mapped_column(String(64))
    taxonomy_version: Mapped[str | None] = mapped_column(String(50))
    model_ids: Mapped[dict[str, Any]]
    adapter_mode: Mapped[str | None] = mapped_column(String(20))
    route: Mapped[str | None] = mapped_column(String(50))
    engine_versions: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default="{}")

    # Spend.
    token_budget: Mapped[int] = mapped_column(BigInteger)
    tokens_used: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0, server_default="0")

    log_uri: Mapped[str | None] = mapped_column(String(1000))
    error: Mapped[str | None] = mapped_column(Text)
    launched_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"))
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class RunSample(UUIDPrimaryKey, CreatedAt, Base):
    """One sample of a run, executed as its own resumable job."""

    __tablename__ = "run_sample"
    __table_args__ = (
        UniqueConstraint("run_id", "sample_index", "epoch"),
        CheckConstraint(f"status IN ({_values(RunStatus)})", name="known_status"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id"))
    sample_index: Mapped[int] = mapped_column(Integer)
    epoch: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    status: Mapped[str] = mapped_column(
        String(20), default=RunStatus.queued.value, server_default=RunStatus.queued.value
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    job_id: Mapped[int | None] = mapped_column(BigInteger)
    heartbeat_at: Mapped[datetime | None]
    tokens_used: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    log_uri: Mapped[str | None] = mapped_column(String(1000))
    error: Mapped[str | None] = mapped_column(Text)
    # What the sample's engine reported beyond tokens, such as signals it dropped.
    detail: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default="{}")


class Transcript(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "transcript"
    __table_args__ = (UniqueConstraint("run_id", "sample_index", "epoch"),)

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id"))
    scenario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scenario.id"))
    sample_index: Mapped[int] = mapped_column(Integer)
    epoch: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    inspect_sample_id: Mapped[str | None] = mapped_column(String(200))
    # Set once the transcript's .eval log is written; empty while a run is live.
    log_uri: Mapped[str | None] = mapped_column(String(1000))
    summary: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default="{}")


class Message(UUIDPrimaryKey, Base):
    __tablename__ = "message"
    __table_args__ = (
        UniqueConstraint("transcript_id", "index"),
        CheckConstraint("role IN ('system', 'user', 'assistant', 'tool')", name="known_role"),
    )

    transcript_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transcript.id"))
    index: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    # A summary written by a separate model, never the raw chain of thought.
    thinking_summary: Mapped[str | None] = mapped_column(Text)
    # Reserved for full thinking, should Anthropic grant access.
    thinking_full: Mapped[str | None] = mapped_column(Text)
    tool_calls: Mapped[list[Any] | None]
    tool_call_id: Mapped[str | None] = mapped_column(String(200))
    model: Mapped[str | None] = mapped_column(String(200))
    meta: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default="{}")

    @property
    def has_full_thinking(self) -> bool:
        return bool(self.thinking_full)


class Score(UUIDPrimaryKey, CreatedAt, Base):
    """A judge's score on one transcript: a Petri dimension or Bloom presence."""

    __tablename__ = "score"
    __table_args__ = (UniqueConstraint("transcript_id", "source", "dimension"),)

    transcript_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transcript.id"))
    source: Mapped[str] = mapped_column(String(50))
    dimension: Mapped[str] = mapped_column(String(100))
    value: Mapped[float] = mapped_column(Float)
    scale_max: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str | None] = mapped_column(Text)
    highlights: Mapped[list[Any]] = mapped_column(default=list, server_default="[]")
    judge_model: Mapped[str | None] = mapped_column(String(200))


class ScenarioSet(UUIDPrimaryKey, CreatedAt, Base):
    """The scenarios and judge dimensions Bloom generated for one behaviour version.

    Written once by its generation run, then read by every Tally run that uses it,
    so each prompt version faces identical scenarios.
    """

    __tablename__ = "scenario_set"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id"), unique=True)
    behaviour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("behaviour.id"), index=True)
    # petri_bloom's Behavior with understanding, scenarios and dimensions filled in.
    content: Mapped[dict[str, Any]]
    content_hash: Mapped[str] = mapped_column(String(64))
    # The generated dimension that scores the behaviour's presence (tagged "behavior").
    presence_dimension: Mapped[str] = mapped_column(String(100))
    scenario_count: Mapped[int] = mapped_column(Integer)
