from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core.config import REPO_ROOT
from agora_core.models import Annotation, DroppedFinding, Message, Run, Transcript
from agora_core.registry import load_registry, sync_registry
from agora_core.storage import get_storage
from testsupport.ethos import dev_judges, ethos_run, inquiry_run, run_ethos, scripted_judges
from testsupport.oidc import FakeOIDCClient, sign_in_as


@pytest.fixture
async def registry(db: AsyncSession) -> None:
    await sync_registry(db, load_registry(REPO_ROOT), "abc123")
    await db.commit()


async def test_the_panel_reads_a_transcript_and_quotes_are_checked(
    client: httpx.AsyncClient,
    idp: FakeOIDCClient,
    registry: None,
    db: AsyncSession,
) -> None:
    source = await inquiry_run(client, idp, db)
    run = await ethos_run(client, source["id"])
    assert run["kind"] == "ethos" and run["taxonomy_version"] == "2026.10.1"
    assert run["model_ids"] == {
        "judge_a": "anthropic/claude-opus-5-5",
        "judge_b": "openai/gpt-6.1-sol",
    }
    assert run["prompt_sha"] == source["prompt_sha"] and run["seed_hash"] == source["seed_hash"]
    await run_ethos(db, run, scripted_judges)

    stored = await db.get(Run, run["id"])
    assert stored is not None
    await db.refresh(stored)
    assert stored.status == "succeeded", stored.error

    annotations = (await db.execute(select(Annotation))).scalars().all()
    assert len(annotations) == 4
    for annotation in annotations:
        message = await db.get(Message, annotation.message_id)
        assert message is not None and message.role == "assistant"
        text_of = message.content if annotation.channel == "content" else message.thinking_summary
        assert text_of is not None
        assert text_of[annotation.char_start : annotation.char_end] == annotation.quote
    assert {a.channel for a in annotations} == {"content", "thinking_summary"}

    dropped = (await db.execute(select(DroppedFinding))).scalars().all()
    assert sorted((d.judge_model, d.reason) for d in dropped) == [
        ("openai/gpt-6.1-sol", "no_valid_answer"),
        ("openai/gpt-6.1-sol", "not_an_agent_reply"),
        ("openai/gpt-6.1-sol", "quote_not_found"),
    ]

    page = (await client.get(f"/api/ethos/runs/{run['id']}")).json()
    assert [item["label"] for item in page["labels"][:3]] == [
        "emotional_reaction",
        "interpretation",
        "exploration",
    ]
    labels = {item["label"]: item for item in page["labels"]}
    assert labels["calibrated_uncertainty"]["expressed"] == 1
    # Two replies: mockllm's tool call carries placeholder text, then the answer.
    assert labels["calibrated_uncertainty"]["replies"] == 2
    assert labels["false_reassurance"]["disputed"] == 1
    assert labels["scope_discipline"]["expressed"] == 0  # thinking summaries never count
    assert {c["judge"]: (c["kept"], c["dropped"]) for c in page["judge_counts"]} == {
        "anthropic/claude-opus-5-5": (3, 0),
        "openai/gpt-6.1-sol": (1, 3),
    }
    assert page["mean_fit"] is not None and page["mean_fit"] < 1
    (summary,) = page["transcripts"]
    assert summary["scenario_type"] == "claim_declined_distress" and summary["disputed"] == 1

    filtered = (
        await client.get(f"/api/ethos/runs/{run['id']}", params={"label": "false_reassurance"})
    ).json()
    assert [e["quote"] for e in filtered["evidence"]] == ["Here is what was decided."]

    view = (
        await client.get(f"/api/ethos/runs/{run['id']}/transcripts/{summary['transcript_id']}")
    ).json()
    reply = view["replies"][-1]
    consensus = {item["label"]: item for item in reply["labels"]}
    assert consensus["calibrated_uncertainty"]["median"] == 1.5
    assert consensus["false_reassurance"]["by_judge"] == {
        "anthropic/claude-opus-5-5": 3,
        "openai/gpt-6.1-sol": 0,
    }
    assert reply["fit"]["intrusions"] == ["false_reassurance"]
    assert len(view["annotations"]) == 4 and view["expected"]
    raw = await get_storage().aget_bytes(f"runs/{run['id']}/samples/0000-judges.json")
    assert b"I would rather not say" in raw

    with pytest.raises(DBAPIError, match="finished run"):
        await db.execute(text("UPDATE annotation SET intensity = 0"))
    await db.rollback()


async def test_ethos_reads_finished_runs_only(
    client: httpx.AsyncClient, idp: FakeOIDCClient, registry: None, db: AsyncSession
) -> None:
    await sign_in_as(client, idp, "admin@example.test")
    response = await client.post(
        "/api/inquiry/runs",
        json={"agent": "claims-assistant", "version": "v2", "seeds": ["legal-threat"]},
    )
    refused = await client.post("/api/ethos/runs", json={"source_run": response.json()["id"]})
    assert refused.status_code == 400 and "finished runs only" in refused.text


async def test_the_development_judges_disagree_and_paraphrase(
    client: httpx.AsyncClient,
    idp: FakeOIDCClient,
    registry: None,
    db: AsyncSession,
) -> None:
    source = await inquiry_run(client, idp, db)
    run = await ethos_run(client, source["id"])
    await run_ethos(db, run, dev_judges)
    page = (await client.get(f"/api/ethos/runs/{run['id']}")).json()
    assert page["run"]["status"] == "succeeded"
    counts = {c["judge"]: c for c in page["judge_counts"]}
    assert counts["anthropic/claude-opus-5-5"]["kept"] > 0
    assert any(d["reason"] == "quote_not_found" for d in page["dropped"])


async def test_compare_two_prompt_versions_on_the_same_scenarios(
    client: httpx.AsyncClient,
    idp: FakeOIDCClient,
    registry: None,
    db: AsyncSession,
) -> None:
    first = await ethos_run(client, (await inquiry_run(client, idp, db, "v1"))["id"])
    second = await ethos_run(client, (await inquiry_run(client, idp, db, "v2"))["id"])
    await run_ethos(db, first, scripted_judges)
    await run_ethos(db, second, dev_judges)
    result = (
        await client.get("/api/ethos/compare", params={"a": first["id"], "b": second["id"]})
    ).json()
    assert result["shared_scenarios"] == 1
    labels = {item["label"]: item for item in result["labels"]}
    assert labels["calibrated_uncertainty"]["a"]["share"] == 0.5  # 1 of 2 replies
    assert labels["calibrated_uncertainty"]["a"]["interval"]["low"] > 0
    assert len(result["scenarios"]) == 1


async def test_the_scanners_run_over_an_inspect_log_directory(
    client: httpx.AsyncClient,
    idp: FakeOIDCClient,
    registry: None,
    db: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same scanners work with Scout alone, over any folder of Inspect logs."""
    from inspect_scout import transcripts_from
    from inspect_scout._display._display import init_display_type
    from inspect_scout.aio import scan_async

    from agora_worker.ethos.scanners import judgement

    await inquiry_run(client, idp, db)
    transcript = (await db.execute(select(Transcript))).scalar_one()
    logs = tmp_path / "logs"
    logs.mkdir()
    key = (transcript.log_uri or "").split("/", 3)[3]
    (logs / "sample.eval").write_bytes(await get_storage().aget_bytes(key))
    monkeypatch.setenv("SCOUT_SCANBUFFER_DIR", str(tmp_path / "buffer"))
    monkeypatch.chdir(tmp_path)
    init_display_type("none")

    status = await scan_async(
        scanners={"judgement": judgement(judge_role="ethos_judge")},
        transcripts=transcripts_from(str(logs)),
        scans=str(tmp_path / "scans"),
        model_roles={
            "ethos_judge": scripted_judges("judge_a", "anthropic/claude-opus-5-5", {}),
        },
        max_processes=1,
    )
    assert status.complete, [e.error for e in status.errors]
    assert status.summary.scanners["judgement"].results >= 1
