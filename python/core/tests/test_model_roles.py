from decimal import Decimal
from pathlib import Path

import pytest

from bench_core.config import REPO_ROOT
from bench_core.model_roles import ModelRolesError, load_model_roles, model_family


def write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "models.yaml"
    path.write_text(body)
    return path


def test_the_committed_roles_load_with_exact_ids() -> None:
    roles = load_model_roles(REPO_ROOT / "config" / "models.yaml")
    assert roles.role("target").model == "anthropic/claude-opus-5-5"
    assert roles.resolved_ids("target", "auditor") == {
        "target": "anthropic/claude-opus-5-5",
        "auditor": "anthropic/claude-opus-5-5",
    }


@pytest.mark.parametrize(
    "model", ["anthropic/claude-latest", "openai/gpt-preview", "anthropic/*", "claude-opus-5-5"]
)
def test_aliases_and_bare_names_are_refused(tmp_path: Path, model: str) -> None:
    with pytest.raises(ModelRolesError):
        load_model_roles(write(tmp_path, f"roles:\n  target:\n    model: {model}\n"))


def test_sampling_settings_are_refused(tmp_path: Path) -> None:
    body = (
        "roles:\n  target:\n    model: anthropic/claude-opus-5-5\n"
        "    generate: {temperature: 0.2}\n"
    )
    with pytest.raises(ModelRolesError, match="repeat samples"):
        load_model_roles(write(tmp_path, body))


def test_missing_roles_are_named(tmp_path: Path) -> None:
    roles = load_model_roles(write(tmp_path, "roles: {}\n"))
    with pytest.raises(ModelRolesError, match="'judge_b'"):
        roles.role("judge_b")


def test_cost_estimates() -> None:
    roles = load_model_roles(REPO_ROOT / "config" / "models.yaml")
    assert roles.cost_usd("anthropic/claude-opus-5-5", 1_000_000, 100_000) == Decimal("6.00")
    assert roles.cost_usd("mockllm/model", 10, 10) == 0


def test_families() -> None:
    assert model_family("anthropic/claude-opus-5-5") == "anthropic"
    assert model_family("openai/gpt-x") == "openai"


def test_production_refuses_development_models(monkeypatch: pytest.MonkeyPatch) -> None:
    from bench_core import model_roles
    from bench_core.config import Environment, Settings

    settings = Settings(
        models_file=Path("config/models.dev.yaml"),
        session_secret="not-the-local-default-but-long-enough",
        public_url="https://bench.example.test",
        environment=Environment.production,
    )
    monkeypatch.setattr(model_roles, "get_settings", lambda: settings)
    model_roles.get_model_roles.cache_clear()
    with pytest.raises(ModelRolesError, match="development models"):
        model_roles.get_model_roles()
    model_roles.get_model_roles.cache_clear()
