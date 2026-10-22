import shutil
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core.config import REPO_ROOT
from agora_core.seeds import (
    SeedError,
    dimension_names,
    load_seeds,
    scenario_for,
    seeds_hash,
    select_seeds,
)


def test_seeds_in_git_load_with_their_metadata() -> None:
    seeds = load_seeds(REPO_ROOT)
    assert len(seeds) >= 20
    seed = seeds["interactions-hopeless"]
    assert seed.agents == ["health-companion"]
    assert seed.content_notes == ["self_harm"]
    assert seed.scenario_type == "risk_signal_present"
    assert not seed.text.startswith("---")


def test_custom_dimensions_are_present() -> None:
    assert dimension_names(REPO_ROOT) == [
        "clinical_overreach",
        "false_reassurance",
        "missed_risk_signal",
        "required_disclosure_omitted",
        "third_party_disclosure",
        "unauthorised_coverage_commitment",
    ]


def test_selection_by_agent_tag_and_key() -> None:
    seeds = load_seeds(REPO_ROOT)
    claims = select_seeds(seeds, agent="claims-assistant", keys=None, tags=None)
    assert claims and all("claims-assistant" in seed.agents for seed in claims)
    privacy = select_seeds(
        seeds, agent="claims-assistant", keys=None, tags=["third_party_disclosure"]
    )
    assert {seed.key for seed in privacy} >= {"spouse-claim-history", "parent-cover-third-party"}
    named = select_seeds(seeds, agent="claims-assistant", keys=["legal-threat"], tags=None)
    assert [seed.key for seed in named] == ["legal-threat"]
    with pytest.raises(SeedError, match="unknown seeds"):
        select_seeds(seeds, agent="claims-assistant", keys=["no-such-seed"], tags=None)


def test_seed_hash_covers_seeds_and_rubrics(tmp_path: Path) -> None:
    shutil.copytree(REPO_ROOT / "seeds", tmp_path / "seeds")
    seeds = load_seeds(tmp_path)
    chosen = [seeds["legal-threat"]]
    before = seeds_hash(tmp_path, chosen)
    rubric = tmp_path / "seeds" / "petri" / "dimensions" / "false_reassurance.md"
    rubric.write_text(rubric.read_text() + "\n- An extra rule.\n")
    assert seeds_hash(tmp_path, chosen) != before


def test_unknown_content_notes_are_refused(tmp_path: Path) -> None:
    folder = tmp_path / "seeds" / "petri" / "seeds"
    folder.mkdir(parents=True)
    (folder / "x.md").write_text("---\ncontent_notes: [gore]\n---\nDo a thing.\n")
    with pytest.raises(SeedError, match="unknown content notes"):
        load_seeds(tmp_path)


async def test_each_seed_text_becomes_one_scenario(db: AsyncSession) -> None:
    seed = load_seeds(REPO_ROOT)["spouse-claim-history"]
    first = await scenario_for(db, seed)
    again = await scenario_for(db, seed)
    assert first.id == again.id
    assert first.domain_tags == ["disputes"]
    assert first.risk_tags == ["third_party_disclosure"]
