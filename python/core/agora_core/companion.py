"""The open-model companion: an open-weight model reads a transcript and reports
per-token signals, so labels Lens reads from the text can be set beside what an
open model's internals show.

A *reader* in config/companion.yaml names the open-weight model, the signals it
reports (probe or persona-vector projections, or natural language autoencoder
explanations) and the Lens label each signal is meant to track. Readers run on the
Droplet runner (infra/runner), which has the GPU; the App Platform worker never
takes the companion queue.

The runner is a command that speaks a small JSON contract on stdin and stdout, so the
GPU code lives in the runner's image and pins its own versions. A reader's
``version`` must match the version the command reports, or Agora refuses the output.
A development reader scores words from a lexicon and needs no GPU; production
refuses it.

Signals are checked in code before they are stored, as Lens quotes are: each must
name a message and a signal the run asked for, and its character offsets must fall
inside that message's text. Signals describe how an open-weight model reads the
conversation. They are not the target model's internals.
"""

from __future__ import annotations

import asyncio
import math
import re
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Protocol

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core import audit
from agora_core.config import Environment, get_settings
from agora_core.lens.runs import READABLE
from agora_core.lens.taxonomy import load_lens, sync_lens
from agora_core.models import FINISHED_STATUSES, Run, RunKind, RunSample, RunStatus, Transcript
from agora_core.provenance import Provenance, config_hash

CONTRACT = "agora.companion/1"
SignalKind = Literal["probe", "persona_vector", "nla"]
NAME = r"^[a-z][a-z0-9_]*$"


class CompanionError(ValueError):
    pass


class RunnerVersionError(CompanionError):
    """The runner reports a different version from the one the run was launched with."""


class SignalSpec(BaseModel):
    """One signal a reader reports, and the Lens label it is meant to track."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=NAME)
    kind: SignalKind
    description: str
    label: str | None = None
    # A reply shows the signal when any of its tokens reaches this value.
    present_at: float | None = None


class ReaderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    runner: Literal["command", "lexicon"]
    version: str
    command: list[str] | None = None
    timeout_seconds: int = Field(default=900, gt=0)
    token_budget: int = Field(default=2_000_000, gt=0)
    signals: list[SignalSpec] = Field(min_length=1)
    lexicon: dict[str, list[str]] | None = None

    @model_validator(mode="after")
    def _runner_fields(self) -> ReaderConfig:
        names = [signal.name for signal in self.signals]
        if len(set(names)) != len(names):
            raise ValueError("signal names must be unique within a reader")
        if self.runner == "command":
            if not self.command:
                raise ValueError("a command reader needs a command")
            if self.lexicon is not None:
                raise ValueError("only lexicon readers take a lexicon")
        else:
            if self.command is not None:
                raise ValueError("a lexicon reader runs no command")
            if not self.lexicon or set(self.lexicon) != set(names):
                raise ValueError("a lexicon reader needs a word list for each of its signals")
        return self

    @property
    def sha256(self) -> str:
        return config_hash(self.model_dump(mode="json"))


class CompanionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readers: dict[str, ReaderConfig] = Field(default_factory=dict)

    def reader(self, key: str) -> ReaderConfig:
        found = self.readers.get(key)
        if found is None:
            raise CompanionError(f"No companion reader called {key!r} in config/companion.yaml.")
        return found


def load_companion(path: Path) -> CompanionConfig:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return CompanionConfig.model_validate(data)
    except (OSError, yaml.YAMLError, ValidationError) as error:
        raise CompanionError(f"{path}: {error}") from error


@lru_cache
def get_companion() -> CompanionConfig:
    settings = get_settings()
    path = settings.companion_file or Path("config/companion.yaml")
    config = load_companion(path if path.is_absolute() else settings.repo_root / path)
    if settings.environment is Environment.production:
        dev = sorted(key for key, r in config.readers.items() if r.runner == "lexicon")
        if dev:
            raise CompanionError(f"development readers cannot be used in production: {dev}")
    return config


# The contract with the runner, as JSON on stdin and stdout.


class CompanionMessage(BaseModel):
    id: str
    index: int
    role: str
    text: str


class CompanionRequest(BaseModel):
    contract: str = CONTRACT
    reader: str
    model: str
    version: str
    signals: list[SignalSpec]
    # The whole conversation in order, for context, and the messages to report on.
    messages: list[CompanionMessage]
    score: list[str]


class TokenValue(BaseModel):
    """One token: its character offsets in the message text, and the signal's value."""

    start: int
    end: int
    value: float


class TokenSignal(BaseModel):
    message_id: str
    name: str
    kind: SignalKind
    # The index of the first token within the message, in the reader's tokenisation.
    token_start: int = Field(ge=0)
    tokens: list[TokenValue] = Field(min_length=1)
    explanation: str | None = None

    @property
    def char_start(self) -> int:
        return self.tokens[0].start

    @property
    def char_end(self) -> int:
        return self.tokens[-1].end


class CompanionResponse(BaseModel):
    contract: str
    runner_version: str
    # Tokens the open model read, counted against the run's budget.
    tokens: int = Field(ge=0)
    signals: list[TokenSignal]


class SignalDrop(StrEnum):
    unknown_message = "unknown_message"
    unknown_signal = "unknown_signal"
    bad_offsets = "bad_offsets"
    bad_value = "bad_value"
    no_explanation = "no_explanation"


def _offsets_fit(tokens: Sequence[TokenValue], length: int) -> bool:
    previous = 0
    for token in tokens:
        if not (previous <= token.start < token.end <= length):
            return False
        previous = token.end
    return True


def check_response(
    response: CompanionResponse, request: CompanionRequest
) -> tuple[list[TokenSignal], Counter[str]]:
    """The signals that hold up, and a count of the rest by reason."""
    if response.contract != CONTRACT:
        raise CompanionError(f"The runner speaks {response.contract!r}, not {CONTRACT!r}.")
    if response.runner_version != request.version:
        raise RunnerVersionError(
            f"The runner reports version {response.runner_version!r}; "
            f"the run was launched for {request.version!r}."
        )
    scored = set(request.score)
    texts = {m.id: m.text for m in request.messages if m.id in scored}
    specs = {spec.name: spec for spec in request.signals}
    kept: list[TokenSignal] = []
    dropped: Counter[str] = Counter()
    for signal in response.signals:
        text = texts.get(signal.message_id)
        spec = specs.get(signal.name)
        if text is None:
            dropped[SignalDrop.unknown_message.value] += 1
        elif spec is None or spec.kind != signal.kind:
            dropped[SignalDrop.unknown_signal.value] += 1
        elif not _offsets_fit(signal.tokens, len(text)):
            dropped[SignalDrop.bad_offsets.value] += 1
        elif not all(math.isfinite(token.value) for token in signal.tokens):
            dropped[SignalDrop.bad_value.value] += 1
        elif signal.kind == "nla" and not (signal.explanation or "").strip():
            dropped[SignalDrop.no_explanation.value] += 1
        else:
            kept.append(signal)
    return kept, dropped


class CompanionRunner(Protocol):
    async def read(self, request: CompanionRequest) -> CompanionResponse: ...


@dataclass(frozen=True)
class CommandRunner:
    """Runs the reader's command on the runner host: request on stdin, response on stdout."""

    command: Sequence[str]
    timeout_seconds: int

    async def read(self, request: CompanionRequest) -> CompanionResponse:
        process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(
                process.communicate(request.model_dump_json().encode("utf-8")),
                self.timeout_seconds,
            )
        except TimeoutError as error:
            process.kill()
            await process.wait()
            raise CompanionError(
                f"The runner took longer than {self.timeout_seconds} seconds."
            ) from error
        if process.returncode != 0:
            tail = err.decode("utf-8", "replace")[-500:]
            raise CompanionError(f"The runner exited with code {process.returncode}: {tail}")
        try:
            return CompanionResponse.model_validate_json(out)
        except ValidationError as error:
            raise CompanionError(
                f"The runner's output does not follow {CONTRACT}: {error}"
            ) from error


TOKEN = re.compile(r"\w+|[^\w\s]")
SENTENCE = re.compile(r"[^.!?]+[.!?]*")


@dataclass(frozen=True)
class LexiconRunner:
    """Development only. Marks tokens found in each signal's word list, so the whole
    path can be followed without a GPU. Its values mean nothing about any model."""

    lexicon: Mapping[str, Sequence[str]]
    version: str

    def _signals(self, message: CompanionMessage, spec: SignalSpec) -> list[TokenSignal]:
        words = {word.lower() for word in self.lexicon.get(spec.name, [])}
        tokens = [(m.start(), m.end()) for m in TOKEN.finditer(message.text)]
        hit = [message.text[start:end].lower() in words for start, end in tokens]
        if spec.kind != "nla":
            if not tokens:
                return []
            values = [
                TokenValue(start=start, end=end, value=0.9 if found else 0.05)
                for (start, end), found in zip(tokens, hit, strict=True)
            ]
            return [
                TokenSignal(
                    message_id=message.id,
                    name=spec.name,
                    kind=spec.kind,
                    token_start=0,
                    tokens=values,
                )
            ]
        found: list[TokenSignal] = []
        for sentence in SENTENCE.finditer(message.text):
            inside = [
                i
                for i, (start, end) in enumerate(tokens)
                if sentence.start() <= start and end <= sentence.end()
            ]
            matched = sorted({message.text[slice(*tokens[i])].lower() for i in inside if hit[i]})
            if not matched:
                continue
            found.append(
                TokenSignal(
                    message_id=message.id,
                    name=spec.name,
                    kind=spec.kind,
                    token_start=inside[0],
                    tokens=[
                        TokenValue(start=tokens[i][0], end=tokens[i][1], value=0.9) for i in inside
                    ],
                    explanation=(
                        "Development reader: this sentence uses words from the "
                        f"{spec.name} list ({', '.join(matched)})."
                    ),
                )
            )
        return found

    async def read(self, request: CompanionRequest) -> CompanionResponse:
        scored = set(request.score)
        signals = [
            signal
            for message in request.messages
            if message.id in scored
            for spec in request.signals
            for signal in self._signals(message, spec)
        ]
        read = sum(len(TOKEN.findall(message.text)) for message in request.messages)
        return CompanionResponse(
            contract=CONTRACT, runner_version=self.version, tokens=read, signals=signals
        )


def runner_for(reader: ReaderConfig) -> CompanionRunner:
    if reader.runner == "command":
        assert reader.command is not None
        return CommandRunner(command=reader.command, timeout_seconds=reader.timeout_seconds)
    assert reader.lexicon is not None
    return LexiconRunner(lexicon=reader.lexicon, version=reader.version)


async def create_companion_run(
    db: AsyncSession,
    *,
    root: Path,
    source: Run,
    companion: CompanionConfig,
    reader_key: str,
    git_commit: str,
    launched_by: uuid.UUID,
    transcript_ids: list[uuid.UUID] | None = None,
) -> tuple[Run, list[RunSample]]:
    if source.kind not in READABLE:
        raise CompanionError("The companion reads Explore, Measure and playground runs.")
    if source.status not in {status.value for status in FINISHED_STATUSES}:
        raise CompanionError("The companion reads finished runs only; this one is still going.")
    reader = companion.reader(reader_key)
    query = (
        select(Transcript)
        .where(Transcript.run_id == source.id)
        .order_by(Transcript.sample_index, Transcript.epoch)
    )
    transcripts = list((await db.execute(query)).scalars())
    if transcript_ids is not None:
        wanted = set(transcript_ids)
        transcripts = [t for t in transcripts if t.id in wanted]
        if len(transcripts) != len(wanted):
            raise CompanionError("Some of those transcripts are not in the source run.")
    if not transcripts:
        raise CompanionError("The source run has no transcripts to read.")

    # Signals are compared with Lens labels, so the run records the taxonomy it maps to.
    spec = load_lens(root)
    taxonomy = await sync_lens(db, spec, git_commit)
    known = {label.key for label in spec.taxonomy.labels}
    unknown = sorted({s.label for s in reader.signals if s.label and s.label not in known})
    if unknown:
        raise CompanionError(f"The reader maps signals to labels Lens does not have: {unknown}")
    config: dict[str, Any] = {
        "engine": "companion",
        "contract": CONTRACT,
        "source_run": str(source.id),
        "source_kind": source.kind,
        "agent": source.config.get("agent"),
        "version": source.config.get("version"),
        "reader": reader_key,
        "reader_config": reader.model_dump(mode="json"),
        "reader_sha": reader.sha256,
        "taxonomy_version": taxonomy.version,
        "taxonomy_sha": taxonomy.sha256,
        "transcripts": [str(t.id) for t in transcripts],
    }
    provenance = Provenance(
        git_commit=git_commit,
        config=config,
        model_ids={"companion": reader.model},
        prompt_sha=source.prompt_sha,
        seed_hash=source.seed_hash,
        taxonomy_version=taxonomy.version,
        engine_versions={"contract": CONTRACT, reader.runner: reader.version},
    )
    provenance.validate()
    run = Run(
        kind=RunKind.companion.value,
        status=RunStatus.queued.value,
        title=f"Companion: {source.title}",
        agent_id=source.agent_id,
        prompt_version_id=source.prompt_version_id,
        tool_profile_id=source.tool_profile_id,
        behaviour_id=source.behaviour_id,
        source_run_id=source.id,
        config=config,
        config_hash=provenance.config_hash,
        git_commit=provenance.git_commit,
        prompt_sha=provenance.prompt_sha,
        seed_hash=provenance.seed_hash,
        taxonomy_version=provenance.taxonomy_version,
        model_ids=provenance.model_ids,
        engine_versions=provenance.engine_versions,
        adapter_mode=source.adapter_mode,
        token_budget=reader.token_budget,
        launched_by=launched_by,
    )
    db.add(run)
    await db.flush()
    samples = [RunSample(run_id=run.id, sample_index=i, epoch=1) for i in range(len(transcripts))]
    db.add_all(samples)
    await db.flush()
    await audit.record(
        db,
        "run.launch",
        actor_id=launched_by,
        target_type="run",
        target_id=run.id,
        detail={"kind": run.kind, "source_run": str(source.id), "samples": len(samples)},
    )
    return run, samples


# Where text-based labels and internal signals agree.


@dataclass(frozen=True)
class Agreement:
    """One signal beside the Lens label it tracks, over the replies both runs read.

    Lens counts a label present in a reply when the panel's median intensity is 1 or
    more; the companion counts a signal present when any token reaches the signal's
    ``present_at``. Each cell lists its replies, so every count leads to evidence.
    """

    signal: str
    kind: str
    label: str
    present_at: float
    both: list[str]
    lens_only: list[str]
    companion_only: list[str]
    neither: list[str]

    @property
    def replies(self) -> int:
        return len(self.both) + len(self.lens_only) + len(self.companion_only) + len(self.neither)

    @property
    def agreement(self) -> float | None:
        """Share of replies where the two agree, present or absent."""
        return (len(self.both) + len(self.neither)) / self.replies if self.replies else None

    @property
    def positive(self) -> float | None:
        """Of the replies either one flags, the share both flag."""
        flagged = len(self.both) + len(self.lens_only) + len(self.companion_only)
        return len(self.both) / flagged if flagged else None


def compare(
    replies: Sequence[str],
    lens: Mapping[str, Mapping[str, float]],
    peaks: Mapping[str, Mapping[str, float]],
    signals: Sequence[SignalSpec],
    lens_present_at: float,
) -> list[Agreement]:
    """``lens`` maps reply to label to the panel's median; ``peaks`` maps reply to
    signal to its highest token value. Signals without a label or threshold are left out."""
    result = []
    for spec in signals:
        if spec.label is None or spec.present_at is None:
            continue
        cells: dict[tuple[bool, bool], list[str]] = {
            (True, True): [],
            (True, False): [],
            (False, True): [],
            (False, False): [],
        }
        for reply in replies:
            by_lens = lens.get(reply, {}).get(spec.label, 0.0) >= lens_present_at
            by_signal = peaks.get(reply, {}).get(spec.name, float("-inf")) >= spec.present_at
            cells[(by_lens, by_signal)].append(reply)
        result.append(
            Agreement(
                signal=spec.name,
                kind=spec.kind,
                label=spec.label,
                present_at=spec.present_at,
                both=cells[(True, True)],
                lens_only=cells[(True, False)],
                companion_only=cells[(False, True)],
                neither=cells[(False, False)],
            )
        )
    return result
