"""Response and request bodies. These shape the OpenAPI schema the web client is generated from."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from bench_core.models import Role


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MeOut(Out):
    id: uuid.UUID
    email: str
    name: str
    roles: list[Role]
    sensitive_opt_in: bool


class MeUpdate(BaseModel):
    sensitive_opt_in: bool


class UserOut(Out):
    id: uuid.UUID
    email: str
    name: str
    roles: list[Role]
    is_active: bool
    sensitive_opt_in: bool
    created_at: datetime
    last_seen_at: datetime | None


class UserUpdate(BaseModel):
    roles: list[Role] | None = None
    is_active: bool | None = None


class AuditEventOut(Out):
    id: int
    at: datetime
    actor_id: uuid.UUID | None
    action: str
    target_type: str | None
    target_id: str | None
    detail: dict[str, Any]


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = Field(
        default=None, description="Pass as `cursor` to fetch the next page."
    )


class SystemCheckOut(Out):
    id: uuid.UUID
    status: str
    requested_by: uuid.UUID | None
    job_id: int | None
    object_key: str | None
    detail: dict[str, Any]
    created_at: datetime
    finished_at: datetime | None


class SignedUrlOut(BaseModel):
    url: str
    expires_in: int


class HealthOut(BaseModel):
    status: str
    environment: str
    commit: str


class ReadinessOut(BaseModel):
    status: str
    database: bool
    queue: bool
