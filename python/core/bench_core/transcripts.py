"""Inspect-format transcripts: written to Spaces as ``.eval`` logs, indexed in Postgres.

Each message is indexed with its visible text and thinking summary pulled apart for
querying, and with the full Inspect message kept in ``meta.inspect`` so that a
conversation can continue exactly (thinking signatures included) and be written
back out as a log.
"""

from __future__ import annotations

import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from inspect_ai.log import (
    EvalConfig,
    EvalDataset,
    EvalLog,
    EvalPlan,
    EvalSample,
    EvalSpec,
    EvalStats,
    read_eval_log_async,
    write_eval_log_async,
)
from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    ChatMessageTool,
    ChatMessageUser,
    GenerateConfig,
    ModelUsage,
)
from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bench_core.agents.adapter import split_assistant
from bench_core.models import Message, Run, Transcript
from bench_core.storage import Storage, object_key

CHAT_MESSAGES: TypeAdapter[list[ChatMessage]] = TypeAdapter(list[ChatMessage])


def log_key(run_id: uuid.UUID, transcript_id: uuid.UUID) -> str:
    return object_key("runs", str(run_id), f"{transcript_id}.eval")


def log_uri(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}"


def key_from_uri(uri: str) -> str:
    return uri.split("/", 3)[3]


def message_row(transcript_id: uuid.UUID, index: int, message: ChatMessage) -> Message:
    thinking: str | None = None
    tool_calls: list[Any] | None = None
    content = message.text
    if isinstance(message, ChatMessageAssistant):
        content, thinking = split_assistant(message)
        if message.tool_calls:
            tool_calls = [call.model_dump(mode="json") for call in message.tool_calls]
    return Message(
        transcript_id=transcript_id,
        index=index,
        role=message.role,
        content=content,
        thinking_summary=thinking,
        tool_calls=tool_calls,
        tool_call_id=message.tool_call_id if isinstance(message, ChatMessageTool) else None,
        model=message.model if isinstance(message, ChatMessageAssistant) else None,
        meta={"inspect": message.model_dump(mode="json", exclude_none=True)},
    )


async def append_messages(
    db: AsyncSession, transcript: Transcript, messages: list[ChatMessage]
) -> list[Message]:
    start = (
        await db.execute(
            select(func.coalesce(func.max(Message.index) + 1, 0)).where(
                Message.transcript_id == transcript.id
            )
        )
    ).scalar_one()
    rows = [message_row(transcript.id, start + i, m) for i, m in enumerate(messages)]
    db.add_all(rows)
    await db.flush()
    return rows


async def load_messages(db: AsyncSession, transcript_id: uuid.UUID) -> list[ChatMessage]:
    rows = (
        await db.execute(
            select(Message.meta)
            .where(Message.transcript_id == transcript_id)
            .order_by(Message.index)
        )
    ).scalars()
    return CHAT_MESSAGES.validate_python([row["inspect"] for row in rows])


def build_log(
    *,
    run: Run,
    transcript: Transcript,
    messages: list[ChatMessage],
    model_id: str,
    generate: dict[str, Any],
    usage: ModelUsage,
    task: str,
    metadata: dict[str, Any],
) -> EvalLog:
    """One sample holding the whole conversation, with the run's provenance attached."""
    now = datetime.now(UTC).isoformat()
    started = (run.started_at or run.created_at or datetime.now(UTC)).isoformat()
    first_user = next(
        (i for i, m in enumerate(messages) if isinstance(m, ChatMessageUser)), len(messages) - 1
    )
    return EvalLog(
        status="success",
        eval=EvalSpec(
            created=started,
            task=task,
            task_id=str(run.id),
            run_id=str(run.id),
            dataset=EvalDataset(name=task, samples=1, sample_ids=[str(transcript.id)]),
            model=model_id,
            config=EvalConfig(),
            metadata=metadata,
        ),
        plan=EvalPlan(name="bench_agent_adapter", config=GenerateConfig(**generate)),
        samples=[
            EvalSample(
                id=str(transcript.id),
                epoch=transcript.epoch,
                input=messages[: first_user + 1],
                target="",
                messages=messages,
                metadata=metadata,
                model_usage={model_id: usage},
            )
        ],
        stats=EvalStats(started_at=started, completed_at=now, model_usage={model_id: usage}),
    )


async def store_log(storage: Storage, log: EvalLog, key: str) -> str:
    with tempfile.TemporaryDirectory(prefix="bench-") as scratch:
        path = Path(scratch) / "transcript.eval"
        await write_eval_log_async(log, location=str(path), format="eval")
        await storage.aput_file(key, path, "application/zip")
    return log_uri(storage.bucket, key)


async def fetch_log(storage: Storage, uri: str) -> EvalLog:
    with tempfile.TemporaryDirectory(prefix="bench-") as scratch:
        path = Path(scratch) / "transcript.eval"
        path.write_bytes(await storage.aget_bytes(key_from_uri(uri)))
        return await read_eval_log_async(str(path))
