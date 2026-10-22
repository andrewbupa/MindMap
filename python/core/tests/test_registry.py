import shutil
from pathlib import Path

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core.config import REPO_ROOT
from agora_core.models import Persona, PromptVersion, ToolProfile
from agora_core.provenance import sha256_text
from agora_core.registry import RegistryError, load_registry, sync_registry, version_sort_key


def test_the_registry_in_git_loads() -> None:
    registry = load_registry(REPO_ROOT)
    assert set(registry) == {"claims-assistant", "health-companion"}
    claims = registry["claims-assistant"]
    assert set(claims.prompts) == {"v1", "v2"}
    v2 = claims.prompts["v2"]
    assert v2.sha256 == sha256_text(v2.text)
    assert not v2.text.startswith("---")
    assert {tool.name for tool in claims.tool_profile.tools} >= {"verify_identity", "get_claim"}
    assert "fixtures/claims.json" in claims.tool_profile.fixtures
    assert claims.personas["declined-mri"].spec.scenario_type == "claim_declined_distress"


def test_version_order_is_numeric() -> None:
    assert sorted(["v10", "v2", "v1.1", "v1"], key=version_sort_key) == ["v1", "v1.1", "v2", "v10"]


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    shutil.copytree(REPO_ROOT / "agents", tmp_path / "agents")
    return tmp_path


def test_mismatched_version_file_is_refused(repo_copy: Path) -> None:
    prompts = repo_copy / "agents" / "claims-assistant" / "prompts"
    (prompts / "v2.md").rename(prompts / "v3.md")
    with pytest.raises(RegistryError, match="must match the file name"):
        load_registry(repo_copy)


def test_fixtures_must_stay_inside_the_agent_folder(repo_copy: Path) -> None:
    tools = repo_copy / "agents" / "claims-assistant" / "tools.json"
    tools.write_text(tools.read_text().replace("fixtures/claims.json", "../../secrets.json"))
    with pytest.raises(RegistryError, match="outside the agent folder"):
        load_registry(repo_copy)


async def test_sync_is_idempotent_and_refuses_edited_prompts(
    db: AsyncSession, repo_copy: Path
) -> None:
    first = await sync_registry(db, load_registry(repo_copy), "abc123")
    await db.commit()
    assert first.agents_added == ["claims-assistant", "health-companion"]
    assert len(first.prompts_added) == 4

    again = await sync_registry(db, load_registry(repo_copy), "def456")
    await db.commit()
    assert not again.changed

    prompt = repo_copy / "agents" / "claims-assistant" / "prompts" / "v1.md"
    prompt.write_text(prompt.read_text() + "\nA quiet edit.\n")
    with pytest.raises(RegistryError, match="immutable"):
        await sync_registry(db, load_registry(repo_copy), "def456")
    await db.rollback()


async def test_changed_personas_and_tools_become_new_rows(
    db: AsyncSession, repo_copy: Path
) -> None:
    await sync_registry(db, load_registry(repo_copy), "abc123")
    await db.commit()
    persona = repo_copy / "agents" / "claims-assistant" / "personas" / "declined-mri.yaml"
    persona.write_text(persona.read_text().replace("Frustrated", "Furious"))
    fixtures = repo_copy / "agents" / "claims-assistant" / "fixtures" / "claims.json"
    fixtures.write_text(fixtures.read_text().replace("495.00", "520.00"))
    report = await sync_registry(db, load_registry(repo_copy), "def456")
    await db.commit()
    assert report.personas_added == ["claims-assistant declined-mri"]
    assert len(report.tool_profiles_added) == 1
    rows = (await db.execute(select(Persona).where(Persona.key == "declined-mri"))).scalars().all()
    assert len(rows) == 2


async def test_stored_prompts_and_profiles_are_write_once(
    db: AsyncSession, repo_copy: Path
) -> None:
    await sync_registry(db, load_registry(repo_copy), "abc123")
    await db.commit()
    for statement in (
        update(PromptVersion).values(text="edited"),
        update(ToolProfile).values(name="edited"),
    ):
        with pytest.raises(DBAPIError, match="append-only"):
            await db.execute(statement)
        await db.rollback()
