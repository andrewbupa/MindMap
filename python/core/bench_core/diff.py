"""Side-by-side line diffs, for comparing prompt versions."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

RowKind = Literal["same", "added", "removed", "changed"]


@dataclass(frozen=True)
class DiffRow:
    kind: RowKind
    left: str | None
    right: str | None
    left_number: int | None
    right_number: int | None


def side_by_side(before: str, after: str) -> list[DiffRow]:
    left, right = before.splitlines(), after.splitlines()
    rows: list[DiffRow] = []
    matcher = SequenceMatcher(a=left, b=right, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            rows.extend(
                DiffRow("same", left[i], right[j], i + 1, j + 1)
                for i, j in zip(range(i1, i2), range(j1, j2), strict=True)
            )
            continue
        span = max(i2 - i1, j2 - j1)
        for k in range(span):
            i, j = i1 + k, j1 + k
            has_left, has_right = i < i2, j < j2
            kind: RowKind = (
                "changed" if has_left and has_right else "removed" if has_left else "added"
            )
            rows.append(
                DiffRow(
                    kind,
                    left[i] if has_left else None,
                    right[j] if has_right else None,
                    i + 1 if has_left else None,
                    j + 1 if has_right else None,
                )
            )
    return rows
