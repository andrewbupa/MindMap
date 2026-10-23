"""Response and request bodies. These shape the OpenAPI schema the web client is generated from."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agora_core.models import Role, Theme


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MeOut(Out):
    id: uuid.UUID
    email: str
    name: str
    roles: list[Role]
    sensitive_opt_in: bool
    theme: Theme


class MeUpdate(BaseModel):
    """Change only what is given."""

    sensitive_opt_in: bool | None = None
    theme: Theme | None = None


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
    route: str | None = Field(description="How the agent was reached, for Tally runs.")
    behaviour_id: uuid.UUID | None
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
    has_full_thinking: bool = Field(
        default=False, description="Full thinking is stored; admins and compliance can read it."
    )
    tool_calls: list[dict[str, Any]] | None
    tool_call_id: str | None
    model: str | None


class RehearsalStart(BaseModel):
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


class RehearsalOut(BaseModel):
    run: RunOut
    agent: str
    version: str
    persona: PersonaOut | None
    messages: list[MessageOut]


class RehearsalSay(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


class RehearsalTurnOut(BaseModel):
    run: RunOut
    messages: list[MessageOut]
    stopped_at_budget: bool


class ModelRoleOut(BaseModel):
    role: str
    model: str
    family: str
    generate: dict[str, Any]


class ProviderOut(BaseModel):
    key: str = Field(description="The family in each model ID, such as anthropic.")
    name: str
    roles: list[str] = Field(description="The roles whose model this provider serves.")
    retention: str
    zero_data_retention: str
    sends_content: bool = Field(description="False for models that run inside Agora.")
    confirmed_by: str | None
    confirmed_on: date | None
    confirmed: bool


class ModelRolesOut(BaseModel):
    roles: list[ModelRoleOut]
    budgets: dict[str, int]
    prices: dict[str, dict[str, float]]
    providers: list[ProviderOut]


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


class InquiryLaunch(BaseModel):
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


class InquiryRunOut(BaseModel):
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


class ReviewIn(BaseModel):
    score_id: uuid.UUID | None = None
    annotation_id: uuid.UUID | None = None
    verdict: str = Field(pattern="^(agree|disagree|unsure)$")
    corrected_value: float | None = Field(default=None, ge=1, le=10)
    corrected_intensity: int | None = Field(default=None, ge=0, le=3)
    notes: str = Field(default="", max_length=5000)


class ReviewOut(Out):
    id: uuid.UUID
    reviewer_id: uuid.UUID
    score_id: uuid.UUID | None
    annotation_id: uuid.UUID | None
    verdict: str
    corrected_value: float | None
    corrected_intensity: int | None
    notes: str
    created_at: datetime


class ScoreReviewItem(BaseModel):
    score: ScoreOut
    transcript_id: uuid.UUID
    run_id: uuid.UUID
    run_title: str
    scenario_key: str | None
    content_notes: list[str]
    reviews: int
    reviewed_by_me: bool


class ReviewQueueOut(BaseModel):
    items: list[ScoreReviewItem]
    hidden_for_content_notes: int = Field(
        description="Items left out because they carry content notes you have not opted in to."
    )


# Tally


class ScenarioSetSummary(Out):
    id: uuid.UUID
    run_id: uuid.UUID
    behaviour_id: uuid.UUID
    created_at: datetime
    scenario_count: int
    presence_dimension: str
    content_hash: str
    behaviour_seed_hash: str
    current: bool = Field(description="Generated from the behaviour as it is in git now.")
    model: str


class BehaviourSummary(BaseModel):
    key: str
    title: str
    definition: str
    agents: list[str]
    tags: list[str]
    variations: list[str]
    num_scenarios: int
    scenario_type: str | None
    content_notes: list[str]
    seed_hash: str
    scenario_set: ScenarioSetSummary | None = Field(
        description="The newest scenario set for this behaviour version."
    )
    generating: RunOut | None = Field(description="A generation run still in progress.")


class GeneratedScenarioOut(BaseModel):
    id: str = Field(description="The sample id Bloom gives the scenario.")
    name: str
    variation: str | None
    seed: str
    scenario_row: uuid.UUID | None


class GeneratedDimensionOut(BaseModel):
    name: str
    description: str
    tags: list[str]
    rubric: str | None
    presence: bool


class ScenarioSetOut(BaseModel):
    summary: ScenarioSetSummary
    behaviour: str
    understanding: str | None
    scientific_motivation: str | None
    scenarios: list[GeneratedScenarioOut]
    dimensions: list[GeneratedDimensionOut]
    generation: RunOut


class TallyOut(BaseModel):
    rollouts: int = Field(description="Rollouts the judge scored.")
    elicited: int = Field(description="Scored rollouts at or above the threshold.")
    unscored: int
    rate: float | None
    mean_score: float | None


class EpochTallyOut(TallyOut):
    epoch: int


class ScenarioTallyOut(TallyOut):
    scenario: str
    variation: str | None


class ElicitationOut(BaseModel):
    threshold: float
    overall: TallyOut
    by_epoch: list[EpochTallyOut]
    spread_low: float | None = Field(description="The lowest repetition's rate.")
    spread_high: float | None = Field(description="The highest repetition's rate.")
    stdev: float | None = Field(description="Sample standard deviation of repetition rates.")


class RolloutOut(BaseModel):
    transcript_id: uuid.UUID
    run_id: uuid.UUID
    version: str
    sample_index: int
    epoch: int
    scenario: str
    variation: str | None
    score: float | None
    score_id: uuid.UUID | None
    summary: str | None
    content_notes: list[str]


class TallyRunSummary(BaseModel):
    run: RunOut
    agent: str
    version: str
    behaviour: str
    scenario_set: uuid.UUID
    suite: str
    counts: dict[str, int]
    elicitation: ElicitationOut


class TallyRunOut(TallyRunSummary):
    samples: list[SampleOut]
    rollouts: list[RolloutOut]
    by_scenario: list[ScenarioTallyOut]


class BehaviourDetail(BehaviourSummary):
    scenario_sets: list[ScenarioSetSummary]
    generations: list[RunOut]
    selected_set: uuid.UUID | None
    runs: list[TallyRunSummary] = Field(description="Tally runs on the selected set.")
    top_rollouts: list[RolloutOut] = Field(description="The highest presence scores.")


class ScenarioGenerate(BaseModel):
    token_budget: int | None = Field(default=None, ge=10_000)


class TallyLaunch(BaseModel):
    agent: str
    versions: list[str] = Field(min_length=1, max_length=10)
    scenario_set: uuid.UUID
    epochs: int = Field(default=3, ge=1, le=10, description="Repetitions of every scenario.")
    max_turns: int = Field(default=15, ge=2, le=60)
    token_budget: int | None = Field(default=None, ge=10_000, description="Per prompt version.")
    compaction: bool = Field(default=True, description="Let Petri summarise long audits.")


# Ethos


class EthosFamilyOut(BaseModel):
    key: str
    name: str
    source: str


class EthosLabelOut(BaseModel):
    key: str
    family: str
    definition: str
    examples: list[str]
    counter_examples: list[str]
    trust_status: str


class TaxonomyOut(BaseModel):
    version: str
    families: list[EthosFamilyOut]
    labels: list[EthosLabelOut]


class EthosSourceOut(BaseModel):
    run: RunOut
    transcripts: int


class EthosLaunch(BaseModel):
    source_run: uuid.UUID
    transcripts: list[uuid.UUID] | None = Field(
        default=None, description="Read only these transcripts; all of them when empty."
    )
    token_budget: int | None = Field(default=None, ge=10_000)


class IntervalOut(BaseModel):
    low: float
    high: float


class LabelPrevalenceOut(BaseModel):
    label: str
    family: str
    trust_status: str
    replies: int
    expressed: int = Field(description="Replies where the panel's median intensity is 1 or more.")
    share: float | None
    interval: IntervalOut | None = Field(description="95% Wilson interval for the share.")
    mean_intensity: float
    disputed: int = Field(description="Replies where judges differ by two points or more.")


class DroppedCountOut(BaseModel):
    judge: str
    reason: str
    count: int


class JudgeCountOut(BaseModel):
    judge: str
    kept: int
    dropped: int


class EthosTranscriptSummary(BaseModel):
    transcript_id: uuid.UUID
    sample_index: int
    epoch: int
    scenario_key: str | None
    scenario_type: str | None
    content_notes: list[str]
    replies: int
    fit: float | None
    disputed: int


class EthosEvidenceOut(BaseModel):
    id: uuid.UUID
    transcript_id: uuid.UUID
    message_id: uuid.UUID
    label: str
    judge: str
    intensity: int
    quote: str
    channel: str


class EthosRunSummary(BaseModel):
    run: RunOut
    source: RunOut
    counts: dict[str, int]
    mean_fit: float | None


class EthosRunOut(EthosRunSummary):
    judges: list[str]
    samples: list[SampleOut]
    labels: list[LabelPrevalenceOut]
    transcripts: list[EthosTranscriptSummary]
    judge_counts: list[JudgeCountOut]
    dropped: list[DroppedCountOut]
    evidence: list[EthosEvidenceOut] = Field(
        description="The findings behind one label, when a label is asked for."
    )


class ConsensusOut(BaseModel):
    label: str
    family: str
    median: float
    by_judge: dict[str, int]
    disputed: bool


class FitOut(BaseModel):
    score: float | None
    matches: list[str]
    misses: list[str]
    intrusions: list[str]
    out_of_band: list[str]


class ReplyEthosOut(BaseModel):
    message_id: uuid.UUID
    index: int
    labels: list[ConsensusOut]
    fit: FitOut | None


class AnnotationOut(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    label: str
    family: str
    judge: str
    intensity: int
    quote: str
    start: int
    end: int
    channel: str
    rationale: str


class ExpectationOut(BaseModel):
    label: str
    family: str
    expect: str
    min: int
    max: int


class EthosTranscriptOut(BaseModel):
    run: RunOut
    source: RunOut
    transcript_id: uuid.UUID
    scenario_key: str | None
    scenario_type: str | None
    seed_text: str | None
    content_notes: list[str]
    judges: list[str]
    messages: list[MessageOut]
    replies: list[ReplyEthosOut]
    annotations: list[AnnotationOut]
    expected: list[ExpectationOut]
    labels: list[EthosLabelOut]
    dropped: list[DroppedCountOut]


class LabelComparisonOut(BaseModel):
    label: str
    family: str
    a: LabelPrevalenceOut
    b: LabelPrevalenceOut
    difference: float | None = Field(description="Share in B minus share in A.")
    difference_interval: IntervalOut | None = Field(
        description="95% interval for the difference, by Newcombe's hybrid score method."
    )


class ScenarioComparisonOut(BaseModel):
    scenario_key: str
    a_fit: float | None
    b_fit: float | None
    a_transcripts: list[uuid.UUID]
    b_transcripts: list[uuid.UUID]


class EthosCompareOut(BaseModel):
    a: EthosRunSummary
    b: EthosRunSummary
    shared_scenarios: int
    labels: list[LabelComparisonOut]
    scenarios: list[ScenarioComparisonOut]


# Gold sets


class GoldSetCreate(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=5000)
    source_run: uuid.UUID
    size: int = Field(default=60, ge=1, le=500)
    seed: int = Field(default=0, description="The same seed always draws the same items.")


class GoldItemsAdd(BaseModel):
    source_run: uuid.UUID
    size: int = Field(default=20, ge=1, le=500)
    seed: int = 0


class GoldSetSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    taxonomy_version: str
    created_at: datetime
    items: int
    fully_labelled: int = Field(description="Items rated by at least two experts.")
    labelled_by_me: int


class GoldItemOut(BaseModel):
    id: uuid.UUID
    transcript_id: uuid.UUID
    scenario_key: str | None
    content_notes: list[str]
    labellers: int
    labelled_by_me: bool


class AgreementOut(BaseModel):
    label: str
    family: str
    comparison: str
    judge_model: str | None
    alpha: float | None
    n_units: int
    computed_at: datetime


class GoldSetOut(GoldSetSummary):
    items_list: list[GoldItemOut]
    hidden_for_content_notes: int
    agreement: list[AgreementOut]
    trust: dict[str, str]


class GoldRatingIn(BaseModel):
    message_id: uuid.UUID
    label: str
    intensity: int = Field(ge=0, le=3)
    quote: str | None = Field(default=None, max_length=2000)


class GoldRatingsIn(BaseModel):
    ratings: list[GoldRatingIn]


class GoldRatingOut(BaseModel):
    message_id: uuid.UUID
    label: str
    intensity: int
    quote: str | None


class GoldItemDetail(BaseModel):
    id: uuid.UUID
    gold_set: uuid.UUID
    gold_set_name: str
    transcript_id: uuid.UUID
    scenario_key: str | None
    seed_text: str | None
    content_notes: list[str]
    messages: list[MessageOut]
    replies: list[uuid.UUID]
    labels: list[EthosLabelOut]
    mine: list[GoldRatingOut] = Field(description="Your ratings only; others stay hidden.")
    next_item: uuid.UUID | None


class EthosDisputeOut(BaseModel):
    ethos_run_id: uuid.UUID
    ethos_run_title: str
    transcript_id: uuid.UUID
    scenario_key: str | None
    message_id: uuid.UUID
    reply_text: str
    label: str
    family: str
    median: float
    by_judge: dict[str, int]
    annotations: list[AnnotationOut]
    reviews: int
    reviewed_by_me: bool


class EthosQueueOut(BaseModel):
    items: list[EthosDisputeOut]
    hidden_for_content_notes: int


class FullThinkingOut(BaseModel):
    message_id: uuid.UUID
    index: int
    thinking_full: str


class WitnessSignalSpecOut(BaseModel):
    name: str
    kind: str
    description: str
    label: str | None
    present_at: float | None


class WitnessReaderOut(BaseModel):
    key: str
    model: str
    runner: str
    version: str
    signals: list[WitnessSignalSpecOut]


class WitnessLaunch(BaseModel):
    source_run: uuid.UUID
    reader: str
    transcripts: list[uuid.UUID] | None = Field(
        default=None, description="Read only these transcripts; all of them when empty."
    )


class WitnessRunSummary(BaseModel):
    run: RunOut
    source: RunOut
    reader: WitnessReaderOut
    counts: dict[str, int]


class WitnessSampleOut(SampleOut):
    detail: dict[str, Any]


class ReplyRefOut(BaseModel):
    message_id: uuid.UUID
    transcript_id: uuid.UUID
    index: int
    scenario_key: str | None
    epoch: int


class SignalAgreementOut(BaseModel):
    signal: str
    kind: str
    label: str
    family: str
    trust_status: str | None
    present_at: float
    replies: int
    agreement: float | None = Field(description="Share of replies where both agree.")
    positive: float | None = Field(description="Of replies either flags, the share both flag.")
    both: list[ReplyRefOut]
    ethos_only: list[ReplyRefOut]
    witness_only: list[ReplyRefOut]
    neither: list[ReplyRefOut]


class WitnessRunOut(WitnessRunSummary):
    samples: list[WitnessSampleOut]
    dropped: dict[str, int]
    ethos_run: RunOut | None = Field(description="The Ethos run the signals are compared with.")
    ethos_runs: list[RunOut] = Field(description="Finished Ethos runs on the same source run.")
    agreements: list[SignalAgreementOut]


class TokenValueOut(BaseModel):
    start: int
    end: int
    value: float


class WitnessSignalOut(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    name: str
    kind: str
    label: str | None
    present_at: float | None
    char_start: int
    char_end: int
    tokens: list[TokenValueOut]
    peak: float
    explanation: str | None


class WitnessTranscriptOut(BaseModel):
    run: RunOut
    reader: WitnessReaderOut
    signals: list[WitnessSignalOut]


class KindSpendOut(BaseModel):
    runs: int
    tokens: int
    cost_usd: float


class MonthSpendOut(BaseModel):
    month: str = Field(description="YYYY-MM, in the spend time zone.")
    runs: int
    tokens: int
    cost_usd: float
    by_kind: dict[str, KindSpendOut]


class SpendOut(BaseModel):
    """Estimated spend by the month runs started, newest first, with empty months."""

    time_zone: str
    months: list[MonthSpendOut]
    unpriced_models: list[str] = Field(
        description="Models a role uses that have no price, so their tokens count as nothing."
    )


class RunEstimateOut(BaseModel):
    """A launch's likely use, from recent finished runs of the same kind."""

    kind: str
    samples: int
    basis_runs: int = Field(description="Finished runs the estimate draws on.")
    basis_samples: int
    tokens_per_sample: int | None = None
    cost_per_sample_usd: float | None = None
    estimated_tokens: int | None = None
    estimated_cost_usd: float | None = None
    default_budget: int


# Home


class RegressionOut(BaseModel):
    """A prompt version whose elicitation rate rose over the version before it, on the
    same behaviour and scenario set. A higher rate of the behaviour is worse."""

    behaviour: str
    behaviour_title: str
    agent: str
    scenario_set: uuid.UUID
    version: str
    run_id: uuid.UUID
    rate: float
    previous_version: str
    previous_run_id: uuid.UUID
    previous_rate: float


class AwaitingOut(BaseModel):
    scores: int = Field(description="Judge scores waiting for your verdict.")
    ethos: int = Field(description="Ethos disagreements waiting for your verdict.")
    gold: int = Field(description="Gold-set transcripts you have not labelled.")
    capped: bool = Field(description="True when a queue holds more than the count shown.")
    hidden_for_content_notes: int


class WeekOut(BaseModel):
    since: datetime
    runs: list[RunOut] = Field(description="The newest runs started in the week.")
    by_kind: dict[str, int] = Field(description="Runs started in the week, by kind.")
    finished: int = Field(
        description="Runs started in the week that succeeded or stopped at budget."
    )
    failed: int
    regressions: list[RegressionOut]
    awaiting: AwaitingOut | None = Field(description="Only for reviewers.")
