"""One transcript read by the whole panel: every judge, every family.

The conversation is rebuilt from what Agora stored, so the judge sees exactly the
text Agora later checks quotes against: each reply's visible words, and its thinking
summary inside ``<thinking_summary>`` tags. Message ids are Agora's own, so the
judge's citations resolve straight to stored messages.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    ContentReasoning,
    ContentText,
    Model,
)
from inspect_ai.model._model import init_model_usage, model_usage

from agora_core.lens.findings import RawFinding
from agora_core.models import Message
from agora_core.transcripts import CHAT_MESSAGES
from agora_worker.lens.scanners import LabelText, judge_family


def judged_messages(rows: Sequence[Message]) -> list[ChatMessage]:
    messages = CHAT_MESSAGES.validate_python([row.meta["inspect"] for row in rows])
    rebuilt: list[ChatMessage] = []
    for row, message in zip(rows, messages, strict=True):
        update: dict[str, Any] = {"id": str(row.id)}
        if isinstance(message, ChatMessageAssistant):
            parts: list[Any] = []
            if row.thinking_summary:
                parts.append(
                    ContentReasoning(reasoning="", summary=row.thinking_summary, redacted=True)
                )
            if row.content:
                parts.append(ContentText(text=row.content))
            update["content"] = parts
        rebuilt.append(message.model_copy(update=update))
    return rebuilt


@dataclass
class PanelReading:
    findings: list[RawFinding] = field(default_factory=list)
    # (judge, family) pairs that gave no usable answer, counted against the judge.
    unanswered: list[tuple[str, str]] = field(default_factory=list)
    raw: dict[str, dict[str, Any]] = field(default_factory=dict)
    usage: dict[str, dict[str, int]] = field(default_factory=dict)
    limit_reached: bool = False
    log_uri: str | None = None

    @property
    def tokens(self) -> int:
        return sum(u["input"] + u["output"] for u in self.usage.values())

    def raw_json(self) -> bytes:
        return json.dumps(self.raw, indent=2, default=str).encode("utf-8")


async def read_with_panel(
    messages: list[ChatMessage],
    labels: Sequence[LabelText],
    families: Sequence[str],
    judges: dict[str, Model],
) -> PanelReading:
    """``judges`` maps each judge's exact model ID to its model."""
    init_model_usage({})
    pairs = [(judge, family) for judge in judges for family in families]
    answers = await asyncio.gather(
        *(judge_family(messages, labels, family, judges[judge]) for judge, family in pairs)
    )
    reading = PanelReading()
    for (judge, family), (result, extract_refs) in zip(pairs, answers, strict=True):
        reading.raw.setdefault(judge, {})[family] = {
            "value": result.value,
            "answer": result.answer,
        }
        if result.parsed is None:
            reading.unanswered.append((judge, family))
            continue
        for item in result.parsed:
            references = extract_refs(item.message)
            reading.findings.append(
                RawFinding(
                    judge=judge,
                    family=family,
                    label=item.label,
                    message_id=references[0].id if references else None,
                    part=item.part,
                    quote=item.quote,
                    intensity=item.intensity,
                    rationale=item.explanation,
                )
            )
    reading.usage = {
        name: {"input": u.input_tokens, "output": u.output_tokens}
        for name, u in model_usage().items()
    }
    return reading
