"""Bloom behaviours from ``seeds/bloom/``, in petri_bloom's folder format.

A behaviour version is the exact content of its folder: ``BEHAVIOR.md`` and any
example transcripts. Their hash is the behaviour's seed hash, which Bloom's authors
ask every metric to cite. Generated scenarios never live in the folder; they are
stored in Postgres as a scenario set (see ``agora_core.tally.suites``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from petri_bloom import Behavior, behavior
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core.models import Behaviour
from agora_core.provenance import files_hash
from agora_core.seeds import CONTENT_NOTES


class BehaviourError(ValueError):
    pass


def behaviours_dir(root: Path) -> Path:
    return root / "seeds" / "bloom"


@dataclass(frozen=True)
class BehaviourSource:
    key: str
    path: Path
    definition: Behavior
    files: tuple[Path, ...]
    seed_hash: str

    @property
    def title(self) -> str:
        return self.key.replace("_", " ").capitalize()

    @property
    def agents(self) -> list[str]:
        return [str(agent) for agent in self.definition.metadata.get("agents") or []]

    @property
    def scenario_type(self) -> str | None:
        value = self.definition.metadata.get("scenario_type")
        return str(value) if value else None

    @property
    def content_notes(self) -> list[str]:
        return [str(note) for note in self.definition.metadata.get("content_notes") or []]

    def suits(self, agent: str) -> bool:
        return not self.agents or agent in self.agents

    def seed_config(self) -> dict[str, Any]:
        """The definition petri_bloom read, as stored on the behaviour row."""
        return self.definition.model_dump(mode="json")


def load_behaviour(folder: Path, root: Path) -> BehaviourSource:
    if (folder / "scenarios").exists():
        raise BehaviourError(
            f"{folder}: generated scenarios belong in Agora, not in the folder; remove scenarios/"
        )
    try:
        definition = behavior(path=folder)
    except (OSError, ValueError) as error:
        raise BehaviourError(f"{folder}: {error}") from error
    if definition.modality != "conversation":
        raise BehaviourError(
            f"{folder}: modality must be conversation; our agents answer their own tools"
        )
    if not definition.description.strip():
        raise BehaviourError(f"{folder}: BEHAVIOR.md has no definition")
    notes = definition.metadata.get("content_notes") or []
    unknown = set(notes) - CONTENT_NOTES
    if unknown:
        raise BehaviourError(f"{folder}: unknown content notes {sorted(unknown)}")
    examples = folder / "examples"
    files = [folder / "BEHAVIOR.md"]
    if examples.is_dir():
        files += sorted(path for path in examples.iterdir() if path.is_file())
    return BehaviourSource(
        key=folder.name,
        path=folder,
        definition=definition,
        files=tuple(files),
        seed_hash=files_hash(files, root),
    )


def load_behaviours(root: Path) -> dict[str, BehaviourSource]:
    folders = sorted(
        path for path in behaviours_dir(root).iterdir() if (path / "BEHAVIOR.md").is_file()
    )
    return {folder.name: load_behaviour(folder, root) for folder in folders}


async def behaviour_row(db: AsyncSession, source: BehaviourSource, git_commit: str) -> Behaviour:
    """The row for this exact behaviour version, created on first use. Never edited."""
    found = (
        await db.execute(
            select(Behaviour).where(
                Behaviour.key == source.key, Behaviour.seed_hash == source.seed_hash
            )
        )
    ).scalar_one_or_none()
    if found is not None:
        return found
    row = Behaviour(
        key=source.key,
        name=source.title,
        definition=source.definition.description,
        seed_config=source.seed_config(),
        seed_hash=source.seed_hash,
        git_commit=git_commit,
    )
    db.add(row)
    await db.flush()
    return row


async def sync_behaviours(db: AsyncSession, root: Path, git_commit: str) -> list[str]:
    """Record every behaviour version in the repository. Returns the keys that were new."""
    new: list[str] = []
    for source in load_behaviours(root).values():
        before = (
            await db.execute(
                select(Behaviour.id).where(
                    Behaviour.key == source.key, Behaviour.seed_hash == source.seed_hash
                )
            )
        ).scalar_one_or_none()
        if before is None:
            await behaviour_row(db, source, git_commit)
            new.append(source.key)
    return new
