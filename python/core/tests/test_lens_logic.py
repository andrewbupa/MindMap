import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core.config import REPO_ROOT
from agora_core.lens.fit import fit
from agora_core.lens.panel import PanelError, check_panel, consensus
from agora_core.lens.quotes import Span, locate, verify
from agora_core.lens.taxonomy import Expect, TaxonomyError, load_lens, sync_lens
from agora_core.models import ExpectedProfile, Label
from agora_core.seeds import load_seeds

# Quote verification


def test_quotes_must_be_exact_substrings() -> None:
    text = "I'm sorry. That's a frightening bill to get."
    assert locate(text, "That's a frightening bill") == Span(11, 36)
    assert text[11:36] == "That's a frightening bill"
    assert locate(text, "that's a frightening bill") is None  # case matters
    assert locate(text, "That\u2019s a frightening bill") is None  # so do curly quotes
    assert locate(text, "a frightening  bill") is None  # and spacing
    assert locate(text, "") is None and locate(text, "   ") is None


def test_repeated_phrases_go_to_different_places() -> None:
    text = "I'm sorry. I really am. I'm sorry."
    used: set[tuple[int, int]] = set()
    first = verify(text, "I'm sorry.", used)
    assert first == Span(0, 10)
    used.add((first.start, first.end))
    second = verify(text, "I'm sorry.", used)
    assert second == Span(24, 34)


# Fit


def profile(**expectations: str) -> dict[str, Expect]:
    return {key: Expect(expect=value) for key, value in expectations.items()}  # type: ignore[arg-type]


def test_fit_counts_matches_misses_and_intrusions() -> None:
    expected = profile(
        emotional_reaction="present", referral="present", sycophancy="absent", padding="either"
    )
    result = fit(expected, {"emotional_reaction": 2, "sycophancy": 1, "padding": 3})
    assert result.matches == ["emotional_reaction"]
    assert result.misses == ["referral"]
    assert result.intrusions == ["sycophancy"]
    assert result.score == pytest.approx(1 / 3)


def test_fit_ignores_either_and_unlisted_labels() -> None:
    assert fit(profile(padding="either"), {"padding": 3, "exploration": 2}).score is None
    assert fit(profile(sycophancy="absent"), {}).score is None


def test_fit_notes_matches_outside_the_band() -> None:
    expected = {"emotional_reaction": Expect(expect="present", min=1, max=2)}
    result = fit(expected, {"emotional_reaction": 3})
    assert result.score == 1.0 and result.out_of_band == ["emotional_reaction"]


def test_a_median_of_half_counts_as_absent() -> None:
    assert fit(profile(referral="present"), {"referral": 0.5}).misses == ["referral"]


# Judge panel


def test_panels_need_two_families() -> None:
    check_panel(["anthropic/claude-opus-5-5", "openai/gpt-x"])
    with pytest.raises(PanelError, match="two model families"):
        check_panel(["anthropic/claude-opus-5-5", "anthropic/claude-sonnet-5-5"])
    with pytest.raises(PanelError, match="two or three"):
        check_panel(["anthropic/claude-opus-5-5"])
    with pytest.raises(PanelError, match="different model"):
        check_panel(["anthropic/a", "anthropic/a", "openai/b"])


def test_consensus_uses_the_median_and_flags_wide_disagreement() -> None:
    judges = ["anthropic/a", "openai/b", "google/c"]
    agreed = consensus(judges, {"anthropic/a": 2, "openai/b": 2, "google/c": 1})
    assert agreed.median == 2 and not agreed.disputed
    split = consensus(judges, {"anthropic/a": 3, "google/c": 1})
    assert split.by_judge == {"anthropic/a": 3, "openai/b": 0, "google/c": 1}
    assert split.median == 1 and split.disputed


# Taxonomy and profiles


def test_the_committed_taxonomy_and_profiles_load() -> None:
    spec = load_lens(REPO_ROOT)
    assert spec.taxonomy.version == "2026.10.1" and len(spec.taxonomy.labels) == 17
    claim = spec.profiles.for_type("claim_declined_distress")
    assert claim["sycophancy"].expect == "absent"
    assert spec.profiles.for_type("unknown_type") == {}


def test_every_seed_and_persona_scenario_type_has_a_profile() -> None:
    spec = load_lens(REPO_ROOT)
    types = {seed.scenario_type for seed in load_seeds(REPO_ROOT).values() if seed.scenario_type}
    assert types <= set(spec.profiles.scenario_types)


@pytest.fixture
def lens_copy(tmp_path: Path) -> Path:
    shutil.copytree(REPO_ROOT / "seeds", tmp_path / "seeds")
    return tmp_path


def test_profiles_must_name_known_labels(lens_copy: Path) -> None:
    path = lens_copy / "seeds" / "lens" / "expected_profiles.yaml"
    path.write_text(
        path.read_text().replace("padding: { expect: absent }", "paddng: { expect: absent }", 1)
    )
    with pytest.raises(TaxonomyError, match="unknown labels"):
        load_lens(lens_copy)


def test_profiles_must_match_the_taxonomy_version(lens_copy: Path) -> None:
    path = lens_copy / "seeds" / "lens" / "expected_profiles.yaml"
    path.write_text(path.read_text().replace('"2026.10.1"', '"2026.09.1"'))
    with pytest.raises(TaxonomyError, match="is for taxonomy"):
        load_lens(lens_copy)


async def test_sync_stores_a_version_once_and_refuses_silent_edits(
    db: AsyncSession, lens_copy: Path
) -> None:
    version = await sync_lens(db, load_lens(lens_copy), "abc")
    again = await sync_lens(db, load_lens(lens_copy), "def")
    assert again.id == version.id
    assert (await db.execute(select(func.count()).select_from(Label))).scalar_one() == 17
    profiles = (await db.execute(select(func.count()).select_from(ExpectedProfile))).scalar_one()
    assert profiles > 30
    path = lens_copy / "seeds" / "lens" / "taxonomy.yaml"
    path.write_text(path.read_text().replace("warmth, compassion", "warmth, kindness"))
    with pytest.raises(TaxonomyError, match="differs from the stored version"):
        await sync_lens(db, load_lens(lens_copy), "ghi")
