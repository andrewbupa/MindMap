"""Quote verification. An Ethos finding must quote its message exactly; code checks it.

Judges sometimes paraphrase, trim punctuation or quote from another message. None
of that is accepted: the quote must be an exact substring of the message it names,
or the finding is dropped and counted against the judge.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DropReason(StrEnum):
    empty = "empty_quote"
    not_found = "quote_not_found"
    unknown_message = "unknown_message"
    not_a_reply = "not_an_agent_reply"
    unknown_label = "unknown_label"
    bad_intensity = "intensity_out_of_range"
    # The judge gave no answer Agora could read for a whole family.
    no_answer = "no_valid_answer"


@dataclass(frozen=True)
class Span:
    start: int
    end: int


def locate(text: str, quote: str, *, after: int = 0) -> Span | None:
    """Character offsets of the first exact occurrence of ``quote`` at or after ``after``."""
    if not quote or not quote.strip():
        return None
    start = text.find(quote, after)
    if start < 0:
        return None
    return Span(start, start + len(quote))


def verify(text: str, quote: str, used: set[tuple[int, int]] | None = None) -> Span | None:
    """Locate a quote, preferring an occurrence not already claimed by another finding,
    so that two findings quoting the same repeated phrase point at different places."""
    span = locate(text, quote)
    if span is None or used is None:
        return span
    first = span
    while span is not None and (span.start, span.end) in used:
        span = locate(text, quote, after=span.start + 1)
    return span or first
