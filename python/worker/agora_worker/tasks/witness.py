"""The witness job: an open-weight model reads one transcript and reports per-token
signals. It runs on the Droplet runner, which takes the witness queue. See
agora_core.witness.

The open model reads the conversation as the target saw it. Thinking summaries are
left out: a separate model wrote them, so they are not part of the conversation.
"""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from procrastinate import RetryStrategy
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core.db import session_scope
from agora_core.ethos.read import is_reply
from agora_core.models import Message, RunSample, WitnessSignal
from agora_core.queue import WITNESS_QUEUE, app
from agora_core.storage import Storage, get_storage, object_key
from agora_core.witness import (
    ReaderConfig,
    RunnerVersionError,
    TokenSignal,
    WitnessConfig,
    WitnessMessage,
    WitnessRequest,
    WitnessRunner,
    check_response,
    get_witness,
    runner_for,
)
from agora_worker.samples import MAX_ATTEMPTS, Claim, SampleChanged, execute

RETRY = RetryStrategy(max_attempts=MAX_ATTEMPTS, wait=30, retry_exceptions={RuntimeError})
RunnerFactory = Callable[[ReaderConfig], WitnessRunner]


@app.task(name="witness_sample", queue=WITNESS_QUEUE, retry=RETRY)
async def witness_sample(run_sample_id: str) -> None:
    await execute_witness_sample(uuid.UUID(run_sample_id))


def raw_key(run_id: uuid.UUID, index: int) -> str:
    return object_key("runs", str(run_id), "samples", f"{index:04d}-witness.json")


@dataclass
class WitnessOutcome:
    signals: list[TokenSignal]
    dropped: Counter[str]
    runner_version: str
    tokens: int
    log_uri: str | None
    # Open-weight models on our own GPU have no per-token price.
    usage: dict[str, dict[str, int]] = field(default_factory=dict)
    limit_reached: bool = False


@dataclass
class WitnessWork:
    claim: Claim
    reader: ReaderConfig
    request: WitnessRequest
    runner: WitnessRunner
    storage: Storage

    async def run(self) -> WitnessOutcome:
        if not self.request.score:
            return WitnessOutcome([], Counter(), self.reader.version, 0, None)
        response = await self.runner.read(self.request)
        # What the runner said, before any checking, kept as evidence beside the signals.
        key = raw_key(self.claim.run_id, self.claim.index)
        await self.storage.aput_bytes(
            key, response.model_dump_json(indent=1).encode("utf-8"), "application/json"
        )
        try:
            kept, dropped = check_response(response, self.request)
        except RunnerVersionError as error:
            raise SampleChanged(str(error)) from error
        return WitnessOutcome(
            signals=kept,
            dropped=dropped,
            runner_version=response.runner_version,
            tokens=response.tokens,
            log_uri=self.storage.uri(key),
        )

    async def record(self, db: AsyncSession, outcome: WitnessOutcome) -> None:
        for signal in outcome.signals:
            db.add(
                WitnessSignal(
                    run_id=self.claim.run_id,
                    message_id=uuid.UUID(signal.message_id),
                    model=self.reader.model,
                    kind=signal.kind,
                    name=signal.name,
                    token_start=signal.token_start,
                    token_end=signal.token_start + len(signal.tokens),
                    char_start=signal.char_start,
                    char_end=signal.char_end,
                    values=[token.value for token in signal.tokens],
                    offsets=[[token.start, token.end] for token in signal.tokens],
                    explanation=signal.explanation,
                )
            )
        sample = await db.get(RunSample, self.claim.sample_id)
        assert sample is not None
        sample.detail = {
            "runner_version": outcome.runner_version,
            "signals": len(outcome.signals),
            "dropped": dict(sorted(outcome.dropped.items())),
        }
        await db.flush()


async def execute_witness_sample(
    sample_id: uuid.UUID,
    *,
    witness: WitnessConfig | None = None,
    runners: RunnerFactory = runner_for,
    storage: Storage | None = None,
) -> None:
    async def plan(claim: Claim) -> WitnessWork:
        config = claim.config
        readers = witness or get_witness()
        reader = readers.readers.get(config["reader"])
        if reader is None or reader.sha256 != config["reader_sha"]:
            raise SampleChanged(f"the reader {config['reader']} changed after launch")
        transcript_id = uuid.UUID(config["transcripts"][claim.index])
        async with session_scope() as db:
            rows = list(
                (
                    await db.execute(
                        select(Message)
                        .where(Message.transcript_id == transcript_id)
                        .order_by(Message.index)
                    )
                ).scalars()
            )
        if not rows:
            raise SampleChanged("the transcript has no messages")
        request = WitnessRequest(
            reader=config["reader"],
            model=reader.model,
            version=reader.version,
            signals=reader.signals,
            messages=[
                WitnessMessage(id=str(row.id), index=row.index, role=row.role, text=row.content)
                for row in rows
            ],
            score=[str(row.id) for row in rows if is_reply(row)],
        )
        return WitnessWork(
            claim=claim,
            reader=reader,
            request=request,
            runner=runners(reader),
            storage=storage or get_storage(),
        )

    await execute(sample_id, plan)
