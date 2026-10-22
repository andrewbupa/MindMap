from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from agora_core.models.base import Base, CreatedAt, UUIDPrimaryKey


class Role(StrEnum):
    author = "author"
    reviewer = "reviewer"
    compliance = "compliance"
    admin = "admin"


ROLE_VALUES = ", ".join(f"'{role.value}'" for role in Role)


class Theme(StrEnum):
    system = "system"
    dark = "dark"
    light = "light"


THEME_VALUES = ", ".join(f"'{theme.value}'" for theme in Theme)


class User(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "user"
    __table_args__ = (
        UniqueConstraint("oidc_issuer", "oidc_subject"),
        CheckConstraint(f"roles <@ ARRAY[{ROLE_VALUES}]::varchar[]", name="known_roles"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint(f"theme IN ({THEME_VALUES})", name="known_theme"),
    )

    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    oidc_issuer: Mapped[str] = mapped_column(String(500))
    oidc_subject: Mapped[str] = mapped_column(String(255))
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list, server_default="{}")
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    # Reviewer care: queues touching self-harm, abuse or bereavement are opt-in.
    sensitive_opt_in: Mapped[bool] = mapped_column(default=False, server_default="false")
    # Dark, light, or whatever the person's device prefers.
    theme: Mapped[str] = mapped_column(String(10), default="system", server_default="system")
    last_seen_at: Mapped[datetime | None]

    def has_role(self, *wanted: Role) -> bool:
        held = set(self.roles)
        return Role.admin.value in held or any(role.value in held for role in wanted)


class UserSession(CreatedAt, Base):
    """A signed-in browser. Only the SHA-256 of the cookie token is stored."""

    __tablename__ = "user_session"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime]
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    id_token_hint: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(String(500))


class AuditEvent(Base):
    """Append-only record of consequential actions. A trigger refuses edits."""

    __tablename__ = "audit_event"
    __table_args__ = (Index(None, "target_type", "target_id"), Index(None, "at"))

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    at: Mapped[datetime] = mapped_column(server_default=func.now())
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"))
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str | None] = mapped_column(String(50))
    target_id: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default="{}")


class ApiToken(UUIDPrimaryKey, CreatedAt, Base):
    """A bearer token for machine clients of the OpenAI-compatible endpoint.
    Only its SHA-256 is stored; the token is shown once, when created."""

    __tablename__ = "api_token"

    name: Mapped[str] = mapped_column(String(200))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    prefix: Mapped[str] = mapped_column(String(12))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    last_used_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]
