"""What we test: agents, their prompt versions and tools, and the situations we test them in."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from bench_core.models.base import Base, CreatedAt, UUIDPrimaryKey


class Domain(StrEnum):
    claims = "claims"
    coverage = "coverage"
    disputes = "disputes"
    health_support = "health_support"


DOMAIN_VALUES = ", ".join(f"'{domain.value}'" for domain in Domain)


class Agent(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "agent"
    __table_args__ = (
        CheckConstraint(f"domains <@ ARRAY[{DOMAIN_VALUES}]::varchar[]", name="known_domains"),
    )

    key: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    owner: Mapped[str] = mapped_column(String(200))
    domains: Mapped[list[str]] = mapped_column(ARRAY(String(32)))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")


class PromptVersion(UUIDPrimaryKey, CreatedAt, Base):
    """A system prompt exactly as the agent receives it. Never edited once stored."""

    __tablename__ = "prompt_version"
    __table_args__ = (
        UniqueConstraint("agent_id", "version"),
        UniqueConstraint("agent_id", "sha256"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent.id"))
    version: Mapped[str] = mapped_column(String(50))
    text: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    git_commit: Mapped[str] = mapped_column(String(64))
    source_path: Mapped[str] = mapped_column(String(500))
    author: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")


class ToolProfile(UUIDPrimaryKey, CreatedAt, Base):
    """Tool schemas an agent sees, and the synthetic fixture behind each tool."""

    __tablename__ = "tool_profile"
    __table_args__ = (UniqueConstraint("agent_id", "sha256"),)

    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent.id"))
    name: Mapped[str] = mapped_column(String(100))
    tools: Mapped[list[Any]]
    fixtures: Mapped[dict[str, Any]]
    sha256: Mapped[str] = mapped_column(String(64))
    git_commit: Mapped[str] = mapped_column(String(64))


class Persona(UUIDPrimaryKey, CreatedAt, Base):
    """A fictional member or patient. Personas are synthetic by rule. A changed persona
    is a new row with a new hash; the newest row for a key is the current one."""

    __tablename__ = "persona"
    __table_args__ = (UniqueConstraint("agent_id", "key", "sha256"),)

    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent.id"))
    key: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    profile: Mapped[dict[str, Any]]
    tone: Mapped[str] = mapped_column(String(200), default="", server_default="")
    risk_flags: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), default=list, server_default="{}"
    )
    sha256: Mapped[str] = mapped_column(String(64))


class Scenario(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "scenario"
    __table_args__ = (UniqueConstraint("key", "sha256"),)

    key: Mapped[str] = mapped_column(String(150))
    title: Mapped[str] = mapped_column(String(300))
    situation: Mapped[str] = mapped_column(Text)
    scenario_type: Mapped[str | None] = mapped_column(String(100))
    domain_tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), default=list, server_default="{}"
    )
    risk_tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), default=list, server_default="{}"
    )
    # Content notes such as self_harm, abuse or bereavement gate reviewer queues.
    content_notes: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), default=list, server_default="{}"
    )
    seed_text: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50))
    persona_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("persona.id"))
    sha256: Mapped[str] = mapped_column(String(64))


class Behaviour(UUIDPrimaryKey, CreatedAt, Base):
    """A Bloom behaviour definition and its seed configuration."""

    __tablename__ = "behaviour"
    __table_args__ = (UniqueConstraint("key", "seed_hash"),)

    key: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    definition: Mapped[str] = mapped_column(Text)
    seed_config: Mapped[dict[str, Any]]
    seed_hash: Mapped[str] = mapped_column(String(64))
    git_commit: Mapped[str] = mapped_column(String(64))
