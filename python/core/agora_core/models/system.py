"""Companion signals (filled by the Droplet runner), data imports and system checks."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from agora_core.models.base import Base, CreatedAt, UUIDPrimaryKey


class CompanionSignal(UUIDPrimaryKey, CreatedAt, Base):
    """Per-token signals from an open-weight model reading a transcript, for one
    companion run. ``values[i]`` belongs to the token at ``offsets[i]``, a pair of
    character offsets into the message text; ``char_start`` and ``char_end`` span them."""

    __tablename__ = "companion_signal"
    __table_args__ = (
        CheckConstraint("kind IN ('probe', 'persona_vector', 'nla')", name="known_kind"),
        Index("ix_companion_signal_run_message", "run_id", "message_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id"))
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("message.id"))
    model: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    token_start: Mapped[int] = mapped_column(Integer)
    token_end: Mapped[int] = mapped_column(Integer)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    values: Mapped[list[Any]]
    offsets: Mapped[list[Any]]
    explanation: Mapped[str | None] = mapped_column(Text)


class DataImport(UUIDPrimaryKey, CreatedAt, Base):
    """Anything brought into Agora from outside git. Blocks until scanned, or approved."""

    __tablename__ = "data_import"
    __table_args__ = (
        CheckConstraint(
            "status IN ('clean', 'blocked', 'approved', 'rejected')", name="known_status"
        ),
    )

    kind: Mapped[str] = mapped_column(String(50))
    filename: Mapped[str] = mapped_column(String(300))
    object_key: Mapped[str] = mapped_column(String(1000))
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))
    findings: Mapped[list[Any]] = mapped_column(default=list, server_default="[]")
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"))
    decided_at: Mapped[datetime | None]


class SystemCheck(UUIDPrimaryKey, CreatedAt, Base):
    """A round trip through queue, worker and storage, launched by an admin."""

    __tablename__ = "system_check"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')", name="known_status"
        ),
    )

    status: Mapped[str] = mapped_column(String(20), default="queued", server_default="queued")
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"))
    job_id: Mapped[int | None] = mapped_column(BigInteger)
    object_key: Mapped[str | None] = mapped_column(String(1000))
    detail: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default="{}")
    finished_at: Mapped[datetime | None]
