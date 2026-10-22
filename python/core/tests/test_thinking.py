"""Full thinking: requested per role, recorded on runs, stored apart from summaries."""

from __future__ import annotations

from pathlib import Path

import pytest
from inspect_ai.model import ChatMessageAssistant, ContentReasoning, ContentText

from agora_core.model_roles import FULL_THINKING_BETA, ModelRolesError, load_model_roles
from agora_core.transcripts import message_row


def roles(tmp_path: Path, body: str):  # type: ignore[no-untyped-def]
    path = tmp_path / "models.yaml"
    path.write_text(body)
    return load_model_roles(path)


def test_full_thinking_adds_the_beta_header_to_what_runs_record(tmp_path: Path) -> None:
    loaded = roles(
        tmp_path,
        "roles:\n  target:\n    model: anthropic/claude-opus-5-5\n"
        "    generate: {reasoning_effort: medium}\n    thinking: full\n",
    )
    target = loaded.role("target")
    assert target.call_generate == {
        "reasoning_effort": "medium",
        "extra_headers": {"anthropic-beta": FULL_THINKING_BETA},
    }
    assert target.generate == {"reasoning_effort": "medium"}


def test_summary_is_the_default_and_full_thinking_is_anthropic_only(tmp_path: Path) -> None:
    plain = roles(tmp_path, "roles:\n  target:\n    model: anthropic/claude-opus-5-5\n")
    assert plain.role("target").thinking == "summary"
    assert plain.role("target").call_generate == {}
    with pytest.raises(ModelRolesError, match="Anthropic"):
        roles(tmp_path, "roles:\n  judge_b:\n    model: openai/gpt-6.1-sol\n    thinking: full\n")


def test_reasoning_is_stored_as_what_it_is() -> None:
    import uuid

    reply = ChatMessageAssistant(
        content=[ContentReasoning(reasoning="Weigh the policy first."), ContentText(text="Hello.")]
    )
    summary = message_row(uuid.uuid4(), 0, reply)
    assert (summary.thinking_summary, summary.thinking_full) == ("Weigh the policy first.", None)
    full = message_row(uuid.uuid4(), 0, reply, "full")
    assert (full.thinking_summary, full.thinking_full) == (None, "Weigh the policy first.")
    assert full.content == "Hello." and full.has_full_thinking
