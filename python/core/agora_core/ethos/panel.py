"""The judge panel: two or three judges from at least two model families.

Each judge's findings are kept. Per reply and label, a judge that reported nothing
counts as intensity 0. Agora reports the median, and flags the label for expert
review when two judges differ by two points or more. No model family judges its own
outputs alone.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from statistics import median

from agora_core.model_roles import model_family

DISAGREEMENT = 2


class PanelError(ValueError):
    pass


def check_panel(judges: list[str]) -> None:
    """Refuse a panel that is too small or drawn from one family. With two families on
    every panel, the target's family can sit on it but never judges alone."""
    if not 2 <= len(judges) <= 3:
        raise PanelError("An Ethos panel needs two or three judges.")
    if len(set(judges)) != len(judges):
        raise PanelError("Each judge on a panel must be a different model.")
    if len({model_family(judge) for judge in judges}) < 2:
        raise PanelError(
            "An Ethos panel needs judges from at least two model families,"
            " so no family judges its own outputs alone."
        )


@dataclass(frozen=True)
class Consensus:
    median: float
    by_judge: dict[str, int]

    @property
    def spread(self) -> int:
        values = list(self.by_judge.values())
        return max(values) - min(values) if values else 0

    @property
    def disputed(self) -> bool:
        return self.spread >= DISAGREEMENT


def consensus(judges: list[str], intensities: Mapping[str, int]) -> Consensus:
    """Combine one label's intensities on one reply. Judges that found nothing give 0."""
    by_judge = {judge: int(intensities.get(judge, 0)) for judge in judges}
    return Consensus(median=float(median(by_judge.values())), by_judge=by_judge)
