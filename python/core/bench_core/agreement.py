"""Krippendorff's alpha, for agreement between experts and between judges and experts.

Implemented from Krippendorff (2011), "Computing Krippendorff's alpha-reliability",
with the coincidence-matrix method. Units are the things labelled (one label on one
reply); coders are the people or judges. Missing values are allowed. A unit with
fewer than two values carries no information about agreement and is left out.

Label trust follows the usual reading: trusted at 0.8 or above, provisional from
0.667, retired below. Too little data leaves a label unrated.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable, Iterable, Mapping
from enum import StrEnum
from itertools import permutations
from typing import Literal

Metric = Literal["nominal", "ordinal", "interval"]

TRUSTED = 0.8
PROVISIONAL = 0.667
MIN_PAIRABLE = 10  # pairable values needed before a label is rated at all


class Trust(StrEnum):
    unrated = "unrated"
    provisional = "provisional"
    trusted = "trusted"
    retired = "retired"


def _coincidences(units: Iterable[Iterable[float]]) -> tuple[dict[tuple[float, float], float], int]:
    o: dict[tuple[float, float], float] = defaultdict(float)
    pairable = 0
    for values in units:
        vals = list(values)
        m = len(vals)
        if m < 2:
            continue
        pairable += m
        for c, k in permutations(vals, 2):
            o[(c, k)] += 1 / (m - 1)
    return o, pairable


def alpha[U: Hashable, C: Hashable](
    data: Mapping[U, Mapping[C, float | None]], metric: Metric = "ordinal"
) -> float | None:
    """Alpha for ``data[unit][coder] = value`` (None or absent for missing).

    Returns None when there is nothing to compare: fewer than two pairable values,
    or every value the same (expected disagreement is zero).
    """
    units = [[v for v in coders.values() if v is not None] for coders in data.values()]
    o, n_total = _coincidences(units)
    if n_total < 2:
        return None
    n: defaultdict[float, float] = defaultdict(float)
    for (c, _k), weight in o.items():
        n[c] += weight
    values = sorted(n)
    if len(values) < 2:
        return None

    def delta(c: float, k: float) -> float:
        if metric == "nominal":
            return 0.0 if c == k else 1.0
        if metric == "interval":
            return (c - k) ** 2
        low, high = min(c, k), max(c, k)
        between = sum(n[g] for g in values if low <= g <= high)
        return (between - (n[c] + n[k]) / 2) ** 2

    total = sum(n.values())
    observed = sum(weight * delta(c, k) for (c, k), weight in o.items()) / total
    expected = sum(n[c] * n[k] * delta(c, k) for c in values for k in values) / (
        total * (total - 1)
    )
    if expected == 0:
        return None
    return 1 - observed / expected


def pairable_values[U: Hashable, C: Hashable](data: Mapping[U, Mapping[C, float | None]]) -> int:
    return sum(
        len(present)
        for present in ([v for v in coders.values() if v is not None] for coders in data.values())
        if len(present) >= 2
    )


def trust(value: float | None, pairable: int) -> Trust:
    if value is None or pairable < MIN_PAIRABLE:
        return Trust.unrated
    if value >= TRUSTED:
        return Trust.trusted
    if value >= PROVISIONAL:
        return Trust.provisional
    return Trust.retired
