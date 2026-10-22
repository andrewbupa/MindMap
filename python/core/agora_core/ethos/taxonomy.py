"""The Ethos taxonomy and expected profiles, from ``seeds/ethos/``, loaded and checked."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core.models import ExpectedProfile, Label, TaxonomyVersion
from agora_core.provenance import canonical_json, sha256_text

INTENSITY_NAMES = ("absent", "faint", "clear", "dominant")


class TaxonomyError(ValueError):
    pass


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Family(Strict):
    name: str
    source: str


class LabelSpec(Strict):
    key: str
    family: str
    definition: str
    examples: list[str] = Field(min_length=2)
    counter_examples: list[str] = Field(min_length=2)


class Taxonomy(Strict):
    version: str
    families: dict[str, Family]
    labels: list[LabelSpec]

    @model_validator(mode="after")
    def _consistent(self) -> Taxonomy:
        keys = [label.key for label in self.labels]
        if len(keys) != len(set(keys)):
            raise ValueError("label keys must be unique")
        unknown = {label.family for label in self.labels} - set(self.families)
        if unknown:
            raise ValueError(f"labels use unknown families: {sorted(unknown)}")
        return self

    def label(self, key: str) -> LabelSpec:
        for label in self.labels:
            if label.key == key:
                return label
        raise TaxonomyError(f"no label {key!r} in taxonomy {self.version}")

    @property
    def sha256(self) -> str:
        return sha256_text(canonical_json(self.model_dump(mode="json")))


class Expect(Strict):
    expect: Literal["present", "absent", "either"]
    min: int = Field(default=1, ge=0, le=3)
    max: int = Field(default=3, ge=0, le=3)

    @model_validator(mode="after")
    def _band(self) -> Expect:
        if self.min > self.max:
            raise ValueError("min must not exceed max")
        return self


class ScenarioProfile(Strict):
    description: str
    expect: dict[str, Expect]


class Profiles(Strict):
    taxonomy_version: str
    scenario_types: dict[str, ScenarioProfile]

    def for_type(self, scenario_type: str) -> dict[str, Expect]:
        profile = self.scenario_types.get(scenario_type)
        return dict(profile.expect) if profile else {}


@dataclass(frozen=True)
class EthosSpec:
    taxonomy: Taxonomy
    profiles: Profiles


def _load(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise TaxonomyError(f"{path}: {error}") from error


def load_ethos(root: Path) -> EthosSpec:
    folder = root / "seeds" / "ethos"
    try:
        taxonomy = Taxonomy.model_validate(_load(folder / "taxonomy.yaml"))
        profiles = Profiles.model_validate(_load(folder / "expected_profiles.yaml"))
    except ValidationError as error:
        raise TaxonomyError(str(error)) from error
    if profiles.taxonomy_version != taxonomy.version:
        raise TaxonomyError(
            f"expected_profiles.yaml is for taxonomy {profiles.taxonomy_version},"
            f" but taxonomy.yaml is {taxonomy.version}"
        )
    known = {label.key for label in taxonomy.labels}
    for name, profile in profiles.scenario_types.items():
        unknown = set(profile.expect) - known
        if unknown:
            raise TaxonomyError(f"scenario type {name} names unknown labels: {sorted(unknown)}")
    return EthosSpec(taxonomy, profiles)


async def sync_ethos(db: AsyncSession, spec: EthosSpec, git_commit: str) -> TaxonomyVersion:
    """Store this taxonomy version once. A version whose content changed is refused."""
    taxonomy = spec.taxonomy
    digest = sha256_text(
        canonical_json(
            {
                "taxonomy": taxonomy.model_dump(mode="json"),
                "profiles": spec.profiles.model_dump(mode="json"),
            }
        )
    )
    stored = (
        await db.execute(select(TaxonomyVersion).where(TaxonomyVersion.version == taxonomy.version))
    ).scalar_one_or_none()
    if stored is not None:
        if stored.sha256 != digest:
            raise TaxonomyError(
                f"taxonomy {taxonomy.version} differs from the stored version. Change the version"
                " in taxonomy.yaml and expected_profiles.yaml when labels or profiles change."
            )
        return stored
    version = TaxonomyVersion(version=taxonomy.version, sha256=digest, git_commit=git_commit)
    db.add(version)
    await db.flush()
    labels: dict[str, Label] = {}
    for spec_label in taxonomy.labels:
        label = Label(
            taxonomy_version_id=version.id,
            key=spec_label.key,
            family=spec_label.family,
            definition=spec_label.definition.strip(),
            examples=list(spec_label.examples),
            counter_examples=list(spec_label.counter_examples),
            source=taxonomy.families[spec_label.family].source,
        )
        db.add(label)
        labels[spec_label.key] = label
    await db.flush()
    for scenario_type, profile in spec.profiles.scenario_types.items():
        for key, expect in profile.expect.items():
            db.add(
                ExpectedProfile(
                    taxonomy_version_id=version.id,
                    scenario_type=scenario_type,
                    label_id=labels[key].id,
                    expectation=expect.expect,
                    intensity_min=expect.min,
                    intensity_max=expect.max,
                )
            )
    await db.flush()
    return version
