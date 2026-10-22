"""The agent registry: what lives in ``agents/`` in git, loaded, checked and synced to Postgres.

Each agent folder holds ``agent.yaml``, ``prompts/<version>.md`` (front matter, then
the system prompt exactly as the agent receives it), ``tools.json`` (tool schemas,
each bound to a synthetic fixture) and ``personas/*.yaml``.

Stored rows are never edited. A changed prompt must be a new version file; a changed
tool profile or persona becomes a new row identified by its hash.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core.models import Agent, Domain, Persona, PromptVersion, ToolProfile
from agora_core.provenance import canonical_json, sha256_text

VERSION_PATTERN = re.compile(r"^v[0-9]+(\.[0-9]+)?$")
KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,99}$")
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


class RegistryError(ValueError):
    pass


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AgentFile(Strict):
    key: str
    name: str
    owner: str
    domains: list[Domain] = Field(min_length=1)
    description: str = ""

    @field_validator("key")
    @classmethod
    def _key(cls, value: str) -> str:
        if not KEY_PATTERN.match(value):
            raise ValueError("keys are lower case letters, digits and hyphens")
        return value


class PromptFrontMatter(Strict):
    version: str
    author: str
    notes: str = ""


class FixtureBinding(Strict):
    """How a tool call is answered from synthetic fixtures.

    - ``respond``: always return this value.
    - ``file`` + ``lookup``: return the record keyed by that argument.
    - add ``match``: compare these arguments with the record's fields and return
      ``returns`` or ``otherwise``.
    - ``omit``: fields never returned, such as those used only for matching.
    """

    file: str | None = None
    lookup: str | None = None
    match: list[str] = Field(default_factory=list)
    returns: dict[str, Any] | None = None
    otherwise: dict[str, Any] | None = None
    omit: list[str] = Field(default_factory=list)
    respond: Any = None


class ToolSpec(Strict):
    name: str
    description: str
    parameters: dict[str, Any]
    fixture: FixtureBinding


class ToolsFile(Strict):
    tools: list[ToolSpec]


class PersonaFile(Strict):
    key: str
    name: str
    summary: str
    scenario_type: str | None = None
    tone: str = ""
    risk_flags: list[str] = Field(default_factory=list)
    content_notes: list[Literal["self_harm", "abuse", "bereavement"]] = Field(default_factory=list)
    profile: dict[str, Any]


@dataclass(frozen=True)
class LoadedPrompt:
    version: str
    author: str
    notes: str
    text: str
    sha256: str
    source_path: str


@dataclass(frozen=True)
class LoadedToolProfile:
    name: str
    tools: list[ToolSpec]
    fixtures: dict[str, Any]
    sha256: str

    def tools_json(self) -> list[dict[str, Any]]:
        return [tool.model_dump(mode="json") for tool in self.tools]


@dataclass(frozen=True)
class LoadedPersona:
    spec: PersonaFile
    sha256: str


@dataclass(frozen=True)
class LoadedAgent:
    spec: AgentFile
    prompts: dict[str, LoadedPrompt]
    tool_profile: LoadedToolProfile
    personas: dict[str, LoadedPersona] = field(default_factory=dict)


def _read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise RegistryError(f"{path}: not valid YAML: {error}") from error


def _validate[M: BaseModel](model: type[M], data: Any, path: Path) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as error:
        raise RegistryError(f"{path}: {error}") from error


def load_prompt(path: Path, repo_root: Path) -> LoadedPrompt:
    raw = path.read_text(encoding="utf-8")
    found = FRONT_MATTER.match(raw)
    if not found:
        raise RegistryError(f"{path}: prompts start with YAML front matter between --- lines")
    meta = _validate(PromptFrontMatter, yaml.safe_load(found.group(1)), path)
    if meta.version != path.stem or not VERSION_PATTERN.match(meta.version):
        raise RegistryError(f"{path}: version must match the file name, like v3.md")
    text = found.group(2).strip()
    if not text:
        raise RegistryError(f"{path}: the prompt is empty")
    return LoadedPrompt(
        version=meta.version,
        author=meta.author,
        notes=meta.notes.strip(),
        text=text,
        sha256=sha256_text(text),
        source_path=path.relative_to(repo_root).as_posix(),
    )


def load_tool_profile(folder: Path) -> LoadedToolProfile:
    path = folder / "tools.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RegistryError(f"{path}: not valid JSON: {error}") from error
    spec = _validate(ToolsFile, data, path)
    names = [tool.name for tool in spec.tools]
    if len(names) != len(set(names)):
        raise RegistryError(f"{path}: tool names must be unique")
    fixtures: dict[str, Any] = {}
    for tool in spec.tools:
        binding = tool.fixture
        if binding.respond is None and not (binding.file and binding.lookup):
            raise RegistryError(f"{path}: {tool.name} needs a fixture file and lookup, or respond")
        if binding.lookup and binding.lookup not in tool.parameters.get("properties", {}):
            raise RegistryError(f"{path}: {tool.name} looks up {binding.lookup}, not a parameter")
        if binding.file and binding.file not in fixtures:
            fixture_path = (folder / binding.file).resolve()
            if folder.resolve() not in fixture_path.parents:
                raise RegistryError(f"{path}: fixture {binding.file} is outside the agent folder")
            fixtures[binding.file] = json.loads(fixture_path.read_text(encoding="utf-8"))
    digest = sha256_text(canonical_json({"tools": data, "fixtures": fixtures}))
    return LoadedToolProfile(name="default", tools=spec.tools, fixtures=fixtures, sha256=digest)


def load_agent(folder: Path, repo_root: Path) -> LoadedAgent:
    spec = _validate(AgentFile, _read_yaml(folder / "agent.yaml"), folder / "agent.yaml")
    if spec.key != folder.name:
        raise RegistryError(f"{folder}: agent key {spec.key} must match its folder name")
    prompts = {
        prompt.version: prompt
        for prompt in (
            load_prompt(path, repo_root) for path in sorted((folder / "prompts").glob("*.md"))
        )
    }
    if not prompts:
        raise RegistryError(f"{folder}: an agent needs at least one prompt version")
    personas: dict[str, LoadedPersona] = {}
    for path in sorted((folder / "personas").glob("*.yaml")):
        persona = _validate(PersonaFile, _read_yaml(path), path)
        if persona.key != path.stem:
            raise RegistryError(f"{path}: persona key must match the file name")
        personas[persona.key] = LoadedPersona(
            spec=persona, sha256=sha256_text(canonical_json(persona.model_dump(mode="json")))
        )
    return LoadedAgent(
        spec=spec, prompts=prompts, tool_profile=load_tool_profile(folder), personas=personas
    )


def load_registry(repo_root: Path) -> dict[str, LoadedAgent]:
    agents_dir = repo_root / "agents"
    return {
        folder.name: load_agent(folder, repo_root)
        for folder in sorted(agents_dir.iterdir())
        if folder.is_dir() and (folder / "agent.yaml").exists()
    }


def version_sort_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.lstrip("v").split("."))


@dataclass
class SyncReport:
    agents_added: list[str] = field(default_factory=list)
    prompts_added: list[str] = field(default_factory=list)
    tool_profiles_added: list[str] = field(default_factory=list)
    personas_added: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(
            self.agents_added
            or self.prompts_added
            or self.tool_profiles_added
            or self.personas_added
        )


async def sync_registry(
    db: AsyncSession, registry: dict[str, LoadedAgent], git_commit: str
) -> SyncReport:
    """Add anything new in git to Postgres. Refuses a prompt version whose text changed."""
    report = SyncReport()
    for key, loaded in registry.items():
        agent = (await db.execute(select(Agent).where(Agent.key == key))).scalar_one_or_none()
        if agent is None:
            agent = Agent(
                key=key,
                name=loaded.spec.name,
                owner=loaded.spec.owner,
                domains=[domain.value for domain in loaded.spec.domains],
                description=loaded.spec.description.strip(),
            )
            db.add(agent)
            await db.flush()
            report.agents_added.append(key)
        else:
            agent.name = loaded.spec.name
            agent.owner = loaded.spec.owner
            agent.domains = [domain.value for domain in loaded.spec.domains]
            agent.description = loaded.spec.description.strip()

        stored = {
            row.version: row
            for row in (
                await db.execute(select(PromptVersion).where(PromptVersion.agent_id == agent.id))
            ).scalars()
        }
        for version, prompt in loaded.prompts.items():
            existing = stored.get(version)
            if existing is not None:
                if existing.sha256 != prompt.sha256:
                    raise RegistryError(
                        f"{prompt.source_path}: {key} {version} differs from the stored version."
                        " Prompt versions are immutable; add a new version file instead."
                    )
                continue
            db.add(
                PromptVersion(
                    agent_id=agent.id,
                    version=version,
                    text=prompt.text,
                    sha256=prompt.sha256,
                    git_commit=git_commit,
                    source_path=prompt.source_path,
                    author=prompt.author,
                    notes=prompt.notes,
                )
            )
            report.prompts_added.append(f"{key} {version}")

        profile = loaded.tool_profile
        known_profile = (
            await db.execute(
                select(ToolProfile.id).where(
                    ToolProfile.agent_id == agent.id, ToolProfile.sha256 == profile.sha256
                )
            )
        ).scalar_one_or_none()
        if known_profile is None:
            db.add(
                ToolProfile(
                    agent_id=agent.id,
                    name=profile.name,
                    tools=profile.tools_json(),
                    fixtures=profile.fixtures,
                    sha256=profile.sha256,
                    git_commit=git_commit,
                )
            )
            report.tool_profiles_added.append(f"{key} {profile.sha256[:12]}")

        for persona_key, persona in loaded.personas.items():
            known_persona = (
                await db.execute(
                    select(Persona.id).where(
                        Persona.agent_id == agent.id,
                        Persona.key == persona_key,
                        Persona.sha256 == persona.sha256,
                    )
                )
            ).scalar_one_or_none()
            if known_persona is None:
                spec = persona.spec
                db.add(
                    Persona(
                        agent_id=agent.id,
                        key=persona_key,
                        name=spec.name,
                        profile={
                            "summary": spec.summary,
                            "scenario_type": spec.scenario_type,
                            "content_notes": list(spec.content_notes),
                            **spec.profile,
                        },
                        tone=spec.tone,
                        risk_flags=list(spec.risk_flags),
                        sha256=persona.sha256,
                    )
                )
                report.personas_added.append(f"{key} {persona_key}")
    await db.flush()
    return report
