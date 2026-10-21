"""Hashes that pin a run to exactly what produced it.

A config hash is the SHA-256 of the config serialised as canonical JSON: keys
sorted, no insignificant whitespace, UTF-8, and no floats that differ only in
representation. Two configs that mean the same thing hash the same.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HEX_SHA256_LENGTH = 64


class ProvenanceError(ValueError):
    pass


def _normalise(value: Any) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProvenanceError("configs may not contain NaN or infinite numbers")
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ProvenanceError("config keys must be strings")
        return {key: _normalise(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_normalise(item) for item in value]
    if value is None or isinstance(value, str | int | bool):
        return value
    raise ProvenanceError(f"cannot hash a value of type {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(_normalise(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def config_hash(config: dict[str, Any]) -> str:
    return sha256_text(canonical_json(config))


def files_hash(paths: list[Path], root: Path) -> str:
    """One hash over several files, stable under reordering, sensitive to names and bytes."""
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(sha256_bytes(path.read_bytes()).encode("ascii") + b"\n")
    return digest.hexdigest()


def current_git_commit(repo_root: Path, fallback: str) -> str:
    """The commit we are running from. Images get it from App Platform, checkouts from git."""
    if fallback and fallback != "unknown":
        return fallback
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


@dataclass(frozen=True)
class Provenance:
    """Everything a run must record. Missing items are explicit ``None``, never omitted."""

    git_commit: str
    config: dict[str, Any]
    model_ids: dict[str, str]
    prompt_sha: str | None = None
    seed_hash: str | None = None
    taxonomy_version: str | None = None
    engine_versions: dict[str, str] = field(default_factory=dict)

    @property
    def config_hash(self) -> str:
        return config_hash(self.config)

    def validate(self) -> None:
        if not self.git_commit or self.git_commit == "unknown":
            raise ProvenanceError("a run needs the git commit it was launched from")
        for name, value in (("prompt_sha", self.prompt_sha), ("seed_hash", self.seed_hash)):
            if value is not None and (
                len(value) != HEX_SHA256_LENGTH or not all(c in "0123456789abcdef" for c in value)
            ):
                raise ProvenanceError(f"{name} must be a lowercase hex SHA-256")
        if not self.model_ids:
            raise ProvenanceError("a run needs at least one resolved model ID")
