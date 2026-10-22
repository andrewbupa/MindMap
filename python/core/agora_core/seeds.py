"""Petri seeds and judge dimensions from ``seeds/petri/``.

A seed is a markdown file: YAML front matter (tags, the agents it suits, a
scenario type for Lens, content notes), then the auditor's instructions. A
dimension is a markdown rubric named by its file. Both are reviewed in git, and
every Explore run records a hash over exactly the files it used.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core.models import Scenario
from agora_core.provenance import files_hash, sha256_text

FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
CONTENT_NOTES = {"self_harm", "abuse", "bereavement"}


class SeedError(ValueError):
    pass


@dataclass(frozen=True)
class Seed:
    key: str
    text: str
    tags: list[str]
    agents: list[str]
    scenario_type: str | None
    content_notes: list[str]
    path: Path
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def sha256(self) -> str:
        return sha256_text(self.path.read_text(encoding="utf-8"))

    @property
    def title(self) -> str:
        return self.key.replace("-", " ").capitalize()


def _parse(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_text(encoding="utf-8")
    found = FRONT_MATTER.match(raw)
    if not found:
        return {}, raw.strip()
    meta = yaml.safe_load(found.group(1)) or {}
    if not isinstance(meta, dict):
        raise SeedError(f"{path}: front matter must be a mapping")
    return meta, found.group(2).strip()


def load_seeds(root: Path) -> dict[str, Seed]:
    seeds: dict[str, Seed] = {}
    for path in sorted((root / "seeds" / "petri" / "seeds").glob("*.md")):
        meta, body = _parse(path)
        if not body:
            raise SeedError(f"{path}: the seed has no instructions")
        notes = list(meta.get("content_notes") or [])
        unknown = set(notes) - CONTENT_NOTES
        if unknown:
            raise SeedError(f"{path}: unknown content notes {sorted(unknown)}")
        seeds[path.stem] = Seed(
            key=path.stem,
            text=body,
            tags=[str(tag) for tag in meta.get("tags") or []],
            agents=[str(agent) for agent in meta.get("agents") or []],
            scenario_type=meta.get("scenario_type"),
            content_notes=notes,
            path=path,
            metadata=meta,
        )
    return seeds


def select_seeds(
    seeds: dict[str, Seed], *, agent: str, keys: list[str] | None, tags: list[str] | None
) -> list[Seed]:
    """Seeds for an agent: named keys, or those carrying any of the tags, or all that suit it."""
    suited = [seed for seed in seeds.values() if not seed.agents or agent in seed.agents]
    if keys:
        missing = sorted(set(keys) - set(seeds))
        if missing:
            raise SeedError(f"unknown seeds: {', '.join(missing)}")
        return [seeds[key] for key in keys]
    if tags:
        return [seed for seed in suited if set(tags) & set(seed.tags)]
    return suited


def dimensions_dir(root: Path) -> Path:
    return root / "seeds" / "petri" / "dimensions"


def dimension_names(root: Path) -> list[str]:
    return sorted(path.stem for path in dimensions_dir(root).glob("*.md"))


def seeds_hash(root: Path, seeds: list[Seed]) -> str:
    """One hash over the seed files a run uses and every custom dimension rubric."""
    paths = [seed.path for seed in seeds] + sorted(dimensions_dir(root).glob("*.md"))
    return files_hash(paths, root)


async def scenario_for(db: AsyncSession, seed: Seed) -> Scenario:
    """The scenario row for this exact seed text, created on first use."""
    digest = seed.sha256
    found = (
        await db.execute(
            select(Scenario).where(Scenario.key == seed.key, Scenario.sha256 == digest)
        )
    ).scalar_one_or_none()
    if found is not None:
        return found
    domain_tags = [
        tag for tag in seed.tags if tag in {"claims", "coverage", "disputes", "health_support"}
    ]
    scenario = Scenario(
        key=seed.key,
        title=seed.title,
        situation=seed.text,
        scenario_type=seed.scenario_type,
        domain_tags=domain_tags,
        risk_tags=[tag for tag in seed.tags if tag not in domain_tags],
        content_notes=seed.content_notes,
        seed_text=seed.text,
        source="agora",
        sha256=digest,
    )
    db.add(scenario)
    await db.flush()
    return scenario
