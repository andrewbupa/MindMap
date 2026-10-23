from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agora_api.main import app
from agora_core.config import REPO_ROOT
from agora_core.model_roles import FULL_THINKING_BETA, get_model_roles, load_model_roles
from agora_core.models import AuditEvent, Message, User
from agora_core.registry import load_registry, sync_registry
from testsupport.ethos import inquiry_run
from testsupport.oidc import FakeOIDCClient, sign_in_as


@pytest.fixture
def full_thinking() -> Iterator[None]:
    """The committed roles, with the target asking for full thinking."""
    roles = load_model_roles(REPO_ROOT / "config" / "models.yaml")
    target = roles.roles["target"].model_copy(update={"thinking": "full"})
    changed = roles.model_copy(update={"roles": {**roles.roles, "target": target}})
    app.dependency_overrides[get_model_roles] = lambda: changed
    yield
    app.dependency_overrides.pop(get_model_roles, None)


async def test_full_thinking_is_stored_apart_and_read_only_by_oversight(
    client: httpx.AsyncClient,
    idp: FakeOIDCClient,
    db: AsyncSession,
    full_thinking: None,
) -> None:
    await sync_registry(db, load_registry(REPO_ROOT), "abc123")
    await db.commit()
    run = await inquiry_run(client, idp, db)
    assert run["config"]["thinking"] == {"target": "full"}
    assert run["config"]["generate"]["target"]["extra_headers"] == {
        "anthropic-beta": FULL_THINKING_BETA
    }
    reply = (
        await db.execute(select(Message).where(Message.thinking_full.is_not(None)))
    ).scalar_one()
    assert reply.thinking_full == "No promises." and reply.thinking_summary is None

    page = (await client.get(f"/api/inquiry/transcripts/{reply.transcript_id}")).json()
    shown = next(m for m in page["messages"] if m["id"] == str(reply.id))
    assert shown["has_full_thinking"] and shown["thinking_summary"] is None
    assert "thinking_full" not in shown

    full = (await client.get(f"/api/inquiry/transcripts/{reply.transcript_id}/thinking")).json()
    assert [item["thinking_full"] for item in full] == ["No promises."]
    events = (
        (
            await db.execute(
                select(AuditEvent).where(AuditEvent.action == "transcript.full_thinking")
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1

    await sign_in_as(client, idp, "rev@example.test")
    await db.execute(
        update(User).where(User.email == "rev@example.test").values(roles=["reviewer"])
    )
    await db.commit()
    refused = await client.get(f"/api/inquiry/transcripts/{reply.transcript_id}/thinking")
    assert refused.status_code == 403
