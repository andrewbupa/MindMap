from pathlib import Path

import pytest

from agora_core.provenance import (
    Provenance,
    ProvenanceError,
    canonical_json,
    config_hash,
    files_hash,
    sha256_text,
)


def test_canonical_json_sorts_keys_and_drops_whitespace() -> None:
    assert canonical_json({"b": 1, "a": [1, 2]}) == '{"a":[1,2],"b":1}'


def test_config_hash_ignores_key_order_and_integral_floats() -> None:
    assert config_hash({"epochs": 3.0, "seed": "x"}) == config_hash({"seed": "x", "epochs": 3})


def test_config_hash_changes_with_any_value() -> None:
    assert config_hash({"epochs": 3}) != config_hash({"epochs": 4})


def test_config_hash_keeps_unicode_exact() -> None:
    assert config_hash({"note": "café"}) != config_hash({"note": "cafe"})


@pytest.mark.parametrize("bad", [{"x": float("nan")}, {"x": float("inf")}, {1: "a"}, {"x": {1}}])
def test_config_hash_refuses_ambiguous_values(bad: dict[object, object]) -> None:
    with pytest.raises(ProvenanceError):
        config_hash(bad)  # type: ignore[arg-type]


def test_files_hash_is_order_independent_but_name_sensitive(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("one")
    (tmp_path / "b.md").write_text("two")
    forward = files_hash([tmp_path / "a.md", tmp_path / "b.md"], tmp_path)
    backward = files_hash([tmp_path / "b.md", tmp_path / "a.md"], tmp_path)
    assert forward == backward
    (tmp_path / "b.md").rename(tmp_path / "c.md")
    assert files_hash([tmp_path / "a.md", tmp_path / "c.md"], tmp_path) != forward


def test_provenance_requires_commit_models_and_hex_hashes() -> None:
    good = Provenance(
        git_commit="abc123",
        config={"k": 1},
        model_ids={"target": "claude-opus-5-5"},
        prompt_sha=sha256_text("prompt"),
    )
    good.validate()
    assert good.config_hash == config_hash({"k": 1})

    with pytest.raises(ProvenanceError, match="git commit"):
        Provenance(git_commit="unknown", config={}, model_ids={"t": "m"}).validate()
    with pytest.raises(ProvenanceError, match="model ID"):
        Provenance(git_commit="abc", config={}, model_ids={}).validate()
    with pytest.raises(ProvenanceError, match="prompt_sha"):
        Provenance(git_commit="abc", config={}, model_ids={"t": "m"}, prompt_sha="ABC").validate()
