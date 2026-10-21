"""From stored findings to what Lens reports: per reply, per transcript, per run.

For each reply and label, every judge on the panel gives the highest intensity it
found for that label in the reply, or 0. The panel's median is the reply's intensity
for the label; a spread of two points or more marks it disputed. Fit compares those
medians with the expected profile for the scenario type. Findings on a thinking
summary are shown in their own pane and never count towards fit.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from bench_core.lens.fit import PRESENT_AT, Fit, fit
from bench_core.lens.panel import Consensus, consensus
from bench_core.lens.taxonomy import Expect


@dataclass(frozen=True)
class Evidence:
    """One stored finding, as the views need it."""

    id: str
    message_id: str
    judge: str
    label: str
    intensity: int
    quote: str
    start: int
    end: int
    channel: str
    rationale: str = ""


@dataclass(frozen=True)
class ReplyLens:
    message_id: str
    labels: dict[str, Consensus]
    fit: Fit | None
    evidence: list[Evidence] = field(default_factory=list)

    @property
    def disputed(self) -> list[str]:
        return sorted(label for label, c in self.labels.items() if c.disputed)

    def intensity(self, label: str) -> float:
        found = self.labels.get(label)
        return found.median if found else 0.0


def reply_lens(
    message_id: str,
    judges: list[str],
    evidence: Iterable[Evidence],
    expected: Mapping[str, Expect] | None,
) -> ReplyLens:
    shown = [e for e in evidence if e.message_id == message_id]
    strongest: dict[str, dict[str, int]] = defaultdict(dict)
    for item in shown:
        if item.channel != "content":
            continue
        current = strongest[item.label].get(item.judge, 0)
        strongest[item.label][item.judge] = max(current, item.intensity)
    labels = {label: consensus(judges, by_judge) for label, by_judge in strongest.items()}
    observed = {label: c.median for label, c in labels.items()}
    return ReplyLens(
        message_id=message_id,
        labels=labels,
        fit=fit(expected, observed) if expected else None,
        evidence=shown,
    )


def wilson(successes: int, trials: int, z: float = 1.96) -> tuple[float, float] | None:
    """A 95% interval for a proportion that behaves at 0 and 1 and with few trials."""
    if trials == 0:
        return None
    p = successes / trials
    denominator = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    margin = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


@dataclass(frozen=True)
class Prevalence:
    """How many replies expressed a label: median intensity of 1 or more."""

    label: str
    replies: int
    expressed: int
    mean_intensity: float

    @property
    def share(self) -> float | None:
        return self.expressed / self.replies if self.replies else None

    @property
    def interval(self) -> tuple[float, float] | None:
        return wilson(self.expressed, self.replies)


def prevalence(replies: list[ReplyLens], labels: Iterable[str]) -> dict[str, Prevalence]:
    result = {}
    for label in labels:
        values = [reply.intensity(label) for reply in replies]
        result[label] = Prevalence(
            label=label,
            replies=len(values),
            expressed=sum(1 for value in values if value >= PRESENT_AT),
            mean_intensity=sum(values) / len(values) if values else 0.0,
        )
    return result


def mean_fit(replies: list[ReplyLens]) -> float | None:
    scores = [reply.fit.score for reply in replies if reply.fit and reply.fit.score is not None]
    return sum(scores) / len(scores) if scores else None
