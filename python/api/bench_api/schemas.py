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


class PromptVersionOut(Out):
    id: uuid.UUID
    version: str
    sha256: str
    git_commit: str
    source_path: str
    author: str
    notes: str
    created_at: datetime


class PromptVersionText(PromptVersionOut):
    text: str


class ToolOut(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]
    fixture: dict[str, Any]


class ToolProfileOut(Out):
    id: uuid.UUID
    name: str
    sha256: str
    tools: list[ToolOut]
    fixture_files: list[str]
    created_at: datetime


class PersonaOut(Out):
    id: uuid.UUID
    key: str
    name: str
    tone: str
    risk_flags: list[str]
    profile: dict[str, Any]
    sha256: str


class AgentSummary(Out):
    key: str
    name: str
    owner: str
    domains: list[str]
    description: str
    versions: list[str]
    latest_version: str
    persona_count: int


class AgentDetail(AgentSummary):
    prompt_versions: list[PromptVersionOut]
    tool_profile: ToolProfileOut
    personas: list[PersonaOut]


class DiffRowOut(BaseModel):
    kind: str
    left: str | None
    right: str | None
    left_number: int | None
    right_number: int | None


class PromptDiffOut(BaseModel):
    agent: str
    base: PromptVersionOut
    head: PromptVersionOut
    rows: list[DiffRowOut]
    added: int
    removed: int
    changed: int


class RunOut(Out):
    id: uuid.UUID
    kind: str
    status: str
    title: str
    config: dict[str, Any]
    config_hash: str
    git_commit: str
    prompt_sha: str | None
    seed_hash: str | None
    taxonomy_version: str | None
    model_ids: dict[str, Any]
    engine_versions: dict[str, Any]
    adapter_mode: str | None
    token_budget: int
    tokens_used: int
    cost_usd: float
    log_uri: str | None
    error: str | None
    launched_by: uuid.UUID | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class MessageOut(Out):
    id: uuid.UUID
    index: int
    role: str
    content: str
    thinking_summary: str | None
    tool_calls: list[dict[str, Any]] | None
    tool_call_id: str | None
    model: str | None


class PlaygroundStart(BaseModel):
    agent: str
    version: str
    persona: str | None = None
    context: str | None = Field(
        default=None,
        max_length=8000,
        description="What the agent's connected systems would show, in deployed mode.",
    )
    mode: str = Field(default="deployed", pattern="^(deployed|open)$")
    system_prompt: str | None = Field(
        default=None, max_length=20000, description="Open mode only: the system prompt to use."
    )


class PlaygroundOut(BaseModel):
    run: RunOut
    agent: str
    version: str
    persona: PersonaOut | None
    messages: list[MessageOut]


class PlaygroundSay(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


class PlaygroundTurnOut(BaseModel):
    run: RunOut
    messages: list[MessageOut]
    stopped_at_budget: bool


class ModelRoleOut(BaseModel):
    role: str
    model: str
    family: str
    generate: dict[str, Any]


class ModelRolesOut(BaseModel):
    roles: list[ModelRoleOut]
    budgets: dict[str, int]
    prices: dict[str, dict[str, float]]


class ApiTokenOut(Out):
    id: uuid.UUID
    name: str
    prefix: str
    created_by: uuid.UUID
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ApiTokenCreated(BaseModel):
    token: str = Field(description="Shown once. Store it as a secret.")
    details: ApiTokenOut


class SeedOut(BaseModel):
    key: str
    title: str
    tags: list[str]
    agents: list[str]
    scenario_type: str | None
    content_notes: list[str]
    text: str
    sha256: str


class ExploreLaunch(BaseModel):
    agent: str
    version: str
    seeds: list[str] | None = Field(default=None, description="Seed keys; empty means use tags.")
    tags: list[str] | None = Field(default=None, description="Use every suitable seed with a tag.")
    max_turns: int = Field(default=30, ge=2, le=60)
    epochs: int = Field(default=1, ge=1, le=10)
    token_budget: int | None = Field(default=None, ge=10_000)
    compaction: bool = Field(default=True, description="Let Petri summarise long audits.")


class SampleOut(Out):
    id: uuid.UUID
    sample_index: int
    epoch: int
    status: str
    attempts: int
    heartbeat_at: datetime | None
    tokens_used: int
    error: str | None


class ScoreOut(Out):
    id: uuid.UUID
    source: str
    dimension: str
    value: float
    scale_max: float
    explanation: str | None
    highlights: list[Any]
    judge_model: str | None


class TranscriptSummary(Out):
    id: uuid.UUID
    sample_index: int
    epoch: int
    scenario_key: str | None
    summary: str | None
    content_notes: list[str]
    scores: dict[str, float]


class ExploreRunOut(BaseModel):
    run: RunOut
    agent: str
    version: str
    seeds: list[str]
    samples: list[SampleOut]
    counts: dict[str, int]
    dimensions: list[str]
    transcripts: list[TranscriptSummary]


class JudgeReference(BaseModel):
    cite: str | None
    message_id: str | None
    message_index: int | None


class TranscriptOut(BaseModel):
    id: uuid.UUID
    run: RunOut
    sample_index: int
    epoch: int
    scenario_key: str | None
    seed_text: str | None
    content_notes: list[str]
    summary: str | None
    highlights: str | None
    references: list[JudgeReference]
    judge_refused: bool
    messages: list[MessageOut]
    scores: list[ScoreOut]


class DimensionOut(BaseModel):
    name: str
    display_name: str
    description: str
    palette: str = Field(description="good-low: higher is worse; good-high: higher is better.")
    custom: bool
    tags: list[str]
