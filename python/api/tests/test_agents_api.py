from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from agora_api.main import app
from agora_api.models_dep import model_factory
from agora_core.config import REPO_ROOT
from agora_core.model_roles import ModelRoles, get_model_roles, load_model_roles
from agora_core.models import Message, User
from agora_core.registry import load_registry, sync_registry
from agora_core.storage import get_storage
from agora_core.transcripts import fetch_log
from testsupport.agents import RecordingModel, answer, tool_call
from testsupport.oidc import FakeOIDCClient, sign_in_as


@pytest.fixture
async def registry(db: AsyncSession) -> None:
    await sync_registry(db, load_registry(REPO_ROOT), "abc123")
    await db.commit()


@pytest.fixture
def model() -> Iterator[RecordingModel]:
    recording = RecordingModel()
    app.dependency_overrides[model_factory] = lambda: lambda model_id: recording
    yield recording
    app.dependency_overrides.pop(model_factory, None)


def with_budget(tokens: int) -> Iterator[None]:
    roles = load_model_roles(REPO_ROOT / "config" / "models.yaml")
    small = ModelRoles(roles=roles.roles, prices=roles.prices, budgets={"rehearsal": tokens})
    app.dependency_overrides[get_model_roles] = lambda: small
    yield
    app.dependency_overrides.pop(get_model_roles, None)


@pytest.fixture
def small_budget() -> Iterator[None]:
    yield from with_budget(1000)


async def test_agents_prompts_and_diff(
    client: httpx.AsyncClient, idp: FakeOIDCClient, registry: None
) -> None:
    await sign_in_as(client, idp, "admin@example.test")
    agents = (await client.get("/api/agents")).json()
    assert [a["key"] for a in agents] == ["claims-assistant", "health-companion"]
    assert agents[0]["versions"] == ["v1", "v2"] and agents[0]["persona_count"] == 3

    detail = (await client.get("/api/agents/claims-assistant")).json()
    assert detail["tool_profile"]["tools"][0]["name"] == "verify_identity"
    assert {p["key"] for p in detail["personas"]} == {
        "declined-mri",
        "excluded-hip",
        "spouse-caller",
    }

    version = (await client.get("/api/agents/claims-assistant/versions/v2")).json()
    assert version["text"].startswith("You are the claims assistant")

    diff = (
        await client.get("/api/agents/claims-assistant/diff", params={"base": "v1", "head": "v2"})
    ).json()
    assert diff["added"] > 0
    assert any(row["kind"] == "same" for row in diff["rows"])
    assert (await client.get("/api/agents/nobody")).status_code == 404


async def test_people_without_a_role_cannot_read_agents(
    client: httpx.AsyncClient, idp: FakeOIDCClient, registry: None
) -> None:
    await sign_in_as(client, idp, "newcomer@example.test")
    assert (await client.get("/api/agents")).status_code == 403


async def test_rehearsal_conversation_becomes_a_read_only_run(
    client: httpx.AsyncClient,
    idp: FakeOIDCClient,
    registry: None,
    model: RecordingModel,
    db: AsyncSession,
) -> None:
    await sign_in_as(client, idp, "admin@example.test")
    started = await client.post(
        "/api/rehearsal",
        json={
            "agent": "claims-assistant",
            "version": "v2",
            "persona": "declined-mri",
            "context": "Signed-in member: TEST-100231",
        },
    )
    assert started.status_code == 201, started.text
    body = started.json()
    run = body["run"]
    assert run["status"] == "running" and run["kind"] == "rehearsal"
    assert run["git_commit"] == "0" * 40
    assert run["model_ids"] == {"target": "anthropic/claude-opus-5-5"}
    assert len(run["prompt_sha"]) == 64 and len(run["config_hash"]) == 64
    assert body["persona"]["key"] == "declined-mri"
    system = body["messages"][0]
    assert system["role"] == "system" and "TEST-100231" in system["content"]

    model.outputs += [
        tool_call("get_claim", claim_id="CLM-TEST-5521"),
        answer("Outpatient imaging is not included in your extras.", thinking="Check the claim."),
    ]
    said = await client.post(
        f"/api/rehearsal/{run['id']}/messages", json={"content": "Why was my MRI declined?"}
    )
    assert said.status_code == 200, said.text
    turn = said.json()
    assert [m["role"] for m in turn["messages"]] == ["user", "assistant", "tool", "assistant"]
    assert turn["messages"][-1]["thinking_summary"] == "Check the claim."
    assert turn["run"]["tokens_used"] == 2 * 1350
    assert turn["run"]["cost_usd"] > 0
    sent = model.calls[0]["input"]
    assert sent[0].role == "system" and sent[-1].text == "Why was my MRI declined?"
    assert model.calls[0]["tools"][0].name == "verify_identity"

    finished = await client.post(f"/api/rehearsal/{run['id']}/finish")
    assert finished.status_code == 200
    assert finished.json()["run"]["status"] == "succeeded"
    log_uri = finished.json()["run"]["log_uri"]
    log = await fetch_log(get_storage(), log_uri)
    assert log.eval.metadata is not None
    assert log.eval.metadata["prompt_sha"] == run["prompt_sha"]
    assert log.samples is not None and len(log.samples[0].messages) == 5

    link = (await client.get(f"/api/runs/{run['id']}/log")).json()
    assert link["url"].startswith("/api/files/")
    download = await client.get(link["url"])
    assert download.status_code == 200 and download.content.startswith(b"PK")
    assert download.headers["content-disposition"] == f'attachment; filename="{run["id"]}.eval"'

    again = await client.post(f"/api/rehearsal/{run['id']}/messages", json={"content": "Hello?"})
    assert again.status_code == 409
    with pytest.raises(DBAPIError, match="finished run"):
        await db.execute(update(Message).values(content="rewritten"))
    await db.rollback()


async def test_rehearsal_stops_cleanly_at_the_budget(
    client: httpx.AsyncClient,
    idp: FakeOIDCClient,
    registry: None,
    model: RecordingModel,
    small_budget: None,
) -> None:
    await sign_in_as(client, idp, "admin@example.test")
    run = (
        await client.post("/api/rehearsal", json={"agent": "health-companion", "version": "v1"})
    ).json()["run"]
    assert run["token_budget"] == 1000
    model.outputs.append(answer("Here is some general information."))
    turn = (
        await client.post(f"/api/rehearsal/{run['id']}/messages", json={"content": "Hi"})
    ).json()
    assert turn["stopped_at_budget"] is True
    assert turn["run"]["status"] == "stopped_at_budget"
    assert turn["run"]["log_uri"]


async def test_open_mode_uses_the_callers_system_prompt(
    client: httpx.AsyncClient, idp: FakeOIDCClient, registry: None, model: RecordingModel
) -> None:
    await sign_in_as(client, idp, "admin@example.test")
    body = (
        await client.post(
            "/api/rehearsal",
            json={
                "agent": "claims-assistant",
                "version": "v1",
                "mode": "open",
                "system_prompt": "You are a helpful assistant.",
            },
        )
    ).json()
    assert body["run"]["adapter_mode"] == "open"
    assert body["messages"][0]["content"] == "You are a helpful assistant."


async def test_only_the_starter_adds_to_a_conversation(
    client: httpx.AsyncClient,
    idp: FakeOIDCClient,
    registry: None,
    model: RecordingModel,
    db: AsyncSession,
) -> None:
    await sign_in_as(client, idp, "admin@example.test")
    run = (
        await client.post("/api/rehearsal", json={"agent": "claims-assistant", "version": "v2"})
    ).json()["run"]
    # A second author signs in on the same client.
    await sign_in_as(client, idp, "author@example.test")
    await db.execute(
        update(User).where(User.email == "author@example.test").values(roles=["author"])
    )
    await db.commit()
    response = await client.post(f"/api/rehearsal/{run['id']}/messages", json={"content": "Hi"})
    assert response.status_code == 403
    assert response.json()["detail"].startswith("Only the person who started this")


async def test_model_roles_are_readable(client: httpx.AsyncClient, idp: FakeOIDCClient) -> None:
    await sign_in_as(client, idp, "admin@example.test")
    roles = (await client.get("/api/models")).json()
    target = next(role for role in roles["roles"] if role["role"] == "target")
    assert target == {
        "role": "target",
        "model": "anthropic/claude-opus-5-5",
        "family": "anthropic",
        "generate": {"reasoning_effort": "medium", "max_tokens": 16000},
    }
    providers = {p["key"]: p for p in roles["providers"]}
    assert "target" in providers["anthropic"]["roles"]
    assert providers["openai"]["roles"] == ["judge_b"]
    assert providers["openai"]["confirmed"] is False and providers["openai"]["confirmed_by"] is None


def _bearer(token: str) -> dict[str, Any]:
    return {"authorization": f"Bearer {token}"}


async def test_openai_compatible_endpoint(
    client: httpx.AsyncClient, idp: FakeOIDCClient, registry: None, model: RecordingModel
) -> None:
    url = "/api/v1/agents/claims-assistant/v2/chat/completions"
    request = {
        "model": "anything",
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": "The member is TEST-100231 and is upset."},
            {"role": "user", "content": "Will my MRI be paid?"},
        ],
    }
    assert (await client.post(url, json=request)).status_code == 401

    await sign_in_as(client, idp, "admin@example.test")
    created = (await client.post("/api/tokens", json={"name": "Bloom rollouts"})).json()
    token = created["token"]
    assert token.startswith("agora_") and created["details"]["prefix"] == token[:12]
    client.cookies.clear()

    model.outputs += [
        tool_call("get_claim", claim_id="CLM-TEST-5521"),
        answer("I can't promise that. Here is what was decided.", thinking="Avoid promising."),
    ]
    response = await client.post(url, json=request, headers=_bearer(token))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["choices"][0]["message"]["content"].startswith("I can't promise")
    assert data["choices"][0]["finish_reason"] == "stop"
    assert data["agora"]["ignored_parameters"] == ["temperature"]
    assert data["agora"]["thinking_summary"] == "Avoid promising."
    assert [step["role"] for step in data["agora"]["steps"]] == ["assistant", "tool"]
    system = model.calls[0]["input"][0]
    assert system.text.startswith("You are the claims assistant")
    assert "<scenario_context>" in system.text and "TEST-100231" in system.text

    model.outputs.append(tool_call("get_claim", claim_id="CLM-TEST-5521"))
    simulated = await client.post(
        url, json={**request, "agora_tool_results": "simulated"}, headers=_bearer(token)
    )
    choice = simulated.json()["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    assert choice["message"]["tool_calls"][0]["function"]["name"] == "get_claim"

    streaming = await client.post(url, json={**request, "stream": True}, headers=_bearer(token))
    assert streaming.status_code == 400

    await sign_in_as(client, idp, "admin@example.test")
    revoked = await client.delete(f"/api/tokens/{created['details']['id']}")
    assert revoked.json()["revoked_at"] is not None
    client.cookies.clear()
    assert (await client.post(url, json=request, headers=_bearer(token))).status_code == 401
