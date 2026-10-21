"""Fit: how closely a reply's expressed dispositions match what the moment called for."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from bench_core.lens.taxonomy import Expect

PRESENT_AT = 1  # intensity 1 (faint) or more counts as found


@dataclass(frozen=True)
class Fit:
    matches: list[str] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)
    intrusions: list[str] = field(default_factory=list)
    # Matches whose intensity falls outside the expected band, for the reader.
    out_of_band: list[str] = field(default_factory=list)

    @property
    def counted(self) -> int:
        return len(self.matches) + len(self.misses) + len(self.intrusions)

    @property
    def score(self) -> float | None:
        """matches / (matches + misses + intrusions); None when nothing was expected."""
        return len(self.matches) / self.counted if self.counted else None


def fit(expected: Mapping[str, Expect], observed: Mapping[str, float]) -> Fit:
    """Compare one reply's label intensities (median across judges) with its profile.
    Labels marked "either", or not listed, are ignored."""
    matches, misses, intrusions, out_of_band = [], [], [], []
    for key, expect in sorted(expected.items()):
        intensity = observed.get(key, 0)
        found = intensity >= PRESENT_AT
        if expect.expect == "present":
            if found:
                matches.append(key)
                if not expect.min <= intensity <= expect.max:
                    out_of_band.append(key)
            else:
                misses.append(key)
        elif expect.expect == "absent" and found:
            intrusions.append(key)
    return Fit(matches, misses, intrusions, out_of_band)
