"""Checking what a judge reported against the transcript, before anything is stored.

A judge names a message, a label from the family it was asked about, a quote and an
intensity. A finding is kept only if the message is one of the agent's replies, the
label belongs to the family, the intensity is 0 to 3, and the quote is an exact
substring of the reply or of its thinking summary. Everything else is dropped with a
reason and counted against the judge. Intensity 0 means "absent" and is not stored.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from agora_core.ethos.quotes import DropReason, Span, verify


class Channel(StrEnum):
    reply = "content"
    thinking_summary = "thinking_summary"


PARTS = {"reply": Channel.reply, "thinking_summary": Channel.thinking_summary}


@dataclass(frozen=True)
class Reply:
    """A message a judge may cite, as Agora stored it."""

    message_id: str
    role: str
    content: str
    thinking_summary: str | None = None

    def text(self, channel: Channel) -> str | None:
        return self.content if channel is Channel.reply else self.thinking_summary


@dataclass(frozen=True)
class RawFinding:
    judge: str
    family: str
    label: str
    message_id: str | None
    part: str
    quote: str
    intensity: int
    rationale: str


@dataclass(frozen=True)
class Verified:
    finding: RawFinding
    channel: Channel
    span: Span


@dataclass(frozen=True)
class Dropped:
    finding: RawFinding
    reason: DropReason


def check(
    findings: Iterable[RawFinding],
    replies: Mapping[str, Reply],
    labels: Mapping[str, set[str]],
) -> tuple[list[Verified], list[Dropped]]:
    """Keep the findings that hold up; drop the rest with a reason.

    ``labels`` maps each family to its label keys. Repeated phrases: a judge quoting
    the same words twice in one reply is pointed at successive occurrences."""
    kept: list[Verified] = []
    dropped: list[Dropped] = []
    used: dict[tuple[str, str, str], set[tuple[int, int]]] = {}
    for finding in findings:
        reply = replies.get(finding.message_id or "")
        channel = PARTS.get(finding.part, Channel.reply)
        reason: DropReason | None = None
        if reply is None:
            reason = DropReason.unknown_message
        elif reply.role != "assistant":
            reason = DropReason.not_a_reply
        elif finding.label not in labels.get(finding.family, set()):
            reason = DropReason.unknown_label
        elif not 0 <= finding.intensity <= 3:
            reason = DropReason.bad_intensity
        elif finding.intensity == 0:
            continue
        elif not finding.quote.strip():
            reason = DropReason.empty
        if reason is not None or reply is None:
            dropped.append(Dropped(finding, reason or DropReason.unknown_message))
            continue
        text = reply.text(channel)
        claimed = used.setdefault((finding.judge, reply.message_id, channel.value), set())
        span = verify(text, finding.quote, claimed) if text else None
        if span is None:
            dropped.append(Dropped(finding, DropReason.not_found))
            continue
        claimed.add((span.start, span.end))
        kept.append(Verified(finding, channel, span))
    return kept, dropped
