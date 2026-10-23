from __future__ import annotations

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core.config import REPO_ROOT
from agora_core.gold import sample
from agora_core.models import User
from agora_core.registry import load_registry, sync_registry
from testsupport.ethos import ethos_run, inquiry_run, run_ethos, scripted_judges
from testsupport.oidc import FakeOIDCClient, sign_in_as

SEEDS = ("declined-mri-promise", "legal-threat", "just-pay-it")


@pytest.fixture
async def registry(db: AsyncSession) -> None:
    await sync_registry(db, load_registry(REPO_ROOT), "abc123")
    await db.commit()


async def sign_in_reviewer(
    client: httpx.AsyncClient, idp: FakeOIDCClient, db: AsyncSession
) -> None:
    await sign_in_as(client, idp, "rev@example.test")
    await db.execute(
        update(User).where(User.email == "rev@example.test").values(roles=["reviewer"])
    )
    await db.commit()


def ratings(item: dict, padding: int) -> list[dict]:
    """Every label on every reply: calibrated uncertainty clear on the last reply only,
    padding at the given intensity everywhere, everything else absent."""
    rows = []
    for message_id in item["replies"]:
        last = message_id == item["replies"][-1]
        for label in item["labels"]:
            value = 0
            if label["key"] == "calibrated_uncertainty" and last:
                value = 2
            if label["key"] == "padding":
                value = padding
            rows.append({"message_id": message_id, "label": label["key"], "intensity": value})
    return rows


def test_the_sample_is_repeatable() -> None:
    import uuid

    ids = [uuid.UUID(int=i) for i in range(100)]
    assert sample(ids, 10, 7) == sample(list(reversed(ids)), 10, 7)
    assert sample(ids, 10, 7) != sample(ids, 10, 8)
    assert len(sample(ids, 500, 1)) == 100


async def test_experts_label_blind_and_agreement_sets_trust(
    client: httpx.AsyncClient,
    idp: FakeOIDCClient,
    registry: None,
    db: AsyncSession,
) -> None:
    source = await inquiry_run(client, idp, db, seeds=SEEDS, epochs=2)
    run = await ethos_run(client, source["id"])
    await run_ethos(db, run, scripted_judges)

    created = await client.post(
        "/api/jury/gold-sets", json={"name": "Claims calibration", "source_run": source["id"]}
    )
    assert created.status_code == 201, created.text
    gold_set = created.json()
    assert gold_set["items"] == 6 and gold_set["taxonomy_version"] == "2026.10.1"
    detail = (await client.get(f"/api/jury/gold-sets/{gold_set['id']}")).json()
    items = detail["items_list"]

    # The first expert (an admin) rates every item; padding everywhere at 1.
    for item in items:
        url = f"/api/jury/gold-sets/{gold_set['id']}/items/{item['id']}"
        page = (await client.get(url)).json()
        assert page["mine"] == [] and len(page["replies"]) == 2
        saved = await client.put(f"{url}/ratings", json={"ratings": ratings(page, padding=1)})
        assert saved.status_code == 200, saved.text

    # The second expert sees none of the first expert's ratings.
    await sign_in_reviewer(client, idp, db)
    first = f"/api/jury/gold-sets/{gold_set['id']}/items/{items[0]['id']}"
    page = (await client.get(first)).json()
    assert page["mine"] == []
    user_message = next(m["id"] for m in page["messages"] if m["role"] == "user")
    refused = await client.put(
        f"{first}/ratings",
        json={"ratings": [{"message_id": user_message, "label": "padding", "intensity": 1}]},
    )
    assert refused.status_code == 400 and "replies" in refused.text
    for item in items:
        url = f"/api/jury/gold-sets/{gold_set['id']}/items/{item['id']}"
        page = (await client.get(url)).json()
        await client.put(f"{url}/ratings", json={"ratings": ratings(page, padding=0)})
    progress = (await client.get("/api/jury/gold-sets")).json()[0]
    assert progress["fully_labelled"] == 6 and progress["labelled_by_me"] == 6

    forbidden = await client.post(f"/api/jury/gold-sets/{gold_set['id']}/agreement")
    assert forbidden.status_code == 403

    await sign_in_as(client, idp, "admin@example.test")
    agreement = (await client.post(f"/api/jury/gold-sets/{gold_set['id']}/agreement")).json()
    found = {(a["label"], a["comparison"], a["judge_model"]): a for a in agreement}
    experts = found[("calibrated_uncertainty", "expert_expert", None)]
    assert experts["alpha"] == pytest.approx(1.0) and experts["n_units"] == 12
    assert found[("padding", "expert_expert", None)]["alpha"] < 0.667
    assert found[("emotional_reaction", "expert_expert", None)]["alpha"] is None
    # Judge A found calibrated uncertainty clear on every last reply, as the experts did.
    judge_a = found[("calibrated_uncertainty", "judge_expert", "anthropic/claude-opus-5-5")]
    assert judge_a["alpha"] == pytest.approx(1.0)
    judge_b = found[("calibrated_uncertainty", "judge_expert", "openai/gpt-6.1-sol")]
    assert judge_b["alpha"] is not None and judge_b["alpha"] < 1.0

    trust = (await client.get(f"/api/jury/gold-sets/{gold_set['id']}")).json()["trust"]
    assert trust["calibrated_uncertainty"] == "trusted"
    assert trust["padding"] == "retired"
    assert trust["emotional_reaction"] == "unrated"
    taxonomy = (await client.get("/api/ethos/taxonomy")).json()
    shown = {label["key"]: label["trust_status"] for label in taxonomy["labels"]}
    assert shown["calibrated_uncertainty"] == "trusted"


async def test_gold_sets_come_from_finished_runs(
    client: httpx.AsyncClient, idp: FakeOIDCClient, registry: None, db: AsyncSession
) -> None:
    from agora_core.ethos.taxonomy import load_ethos, sync_ethos

    await sync_ethos(db, load_ethos(REPO_ROOT), "abc123")
    await db.commit()
    await sign_in_as(client, idp, "admin@example.test")
    queued = await client.post(
        "/api/inquiry/runs",
        json={"agent": "claims-assistant", "version": "v2", "seeds": ["legal-threat"]},
    )
    refused = await client.post(
        "/api/jury/gold-sets", json={"name": "Too soon", "source_run": queued.json()["id"]}
    )
    assert refused.status_code == 400 and "finished runs" in refused.text
