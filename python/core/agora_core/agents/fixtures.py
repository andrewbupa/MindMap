"""Answer tool calls from an agent's synthetic fixtures, deterministically."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    content: str
    error: str | None = None


def _norm(value: Any) -> str:
    return str(value).strip().casefold()


class FixtureExecutor:
    """Executes tool calls against the fixtures stored with a tool profile."""

    def __init__(self, tools: list[dict[str, Any]], fixtures: dict[str, Any]) -> None:
        self._bindings = {tool["name"]: tool["fixture"] for tool in tools}
        self._fixtures = fixtures

    def has(self, name: str) -> bool:
        return name in self._bindings

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        binding = self._bindings.get(name)
        if binding is None:
            return ToolResult(content="", error=f"Unknown tool {name}.")
        if binding.get("respond") is not None:
            return ToolResult(content=json.dumps(binding["respond"]))

        records: dict[str, Any] = self._fixtures.get(binding["file"], {})
        key = arguments.get(binding["lookup"])
        record = None if key is None else records.get(str(key))
        if record is None and key is not None:
            # Lookups forgive case and surrounding spaces, as a real system would.
            record = next((v for k, v in records.items() if _norm(k) == _norm(key)), None)

        if binding.get("match"):
            matched = isinstance(record, dict) and all(
                _norm(record.get(field, "")) == _norm(arguments.get(field, ""))
                for field in binding["match"]
            )
            outcome = binding.get("returns") if matched else binding.get("otherwise")
            return ToolResult(content=json.dumps(outcome if outcome is not None else matched))

        if record is None:
            return ToolResult(
                content=json.dumps({"error": f"No record found for {binding['lookup']} {key!r}."})
            )
        if isinstance(record, dict) and binding.get("omit"):
            record = {k: v for k, v in record.items() if k not in binding["omit"]}
        return ToolResult(content=json.dumps(record))
