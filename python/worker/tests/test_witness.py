from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from agora_api.main import app
from agora_core.config import REPO_ROOT
from agora_core.models import Message, RunSample, WitnessSignal
from agora_core.registry import load_registry, sync_registry
from agora_core.witness import (
    LexiconRunner,
    ReaderConfig,
    WitnessConfig,
    get_witness,
    load_witness,
)
from agora_worker.tasks.witness import execute_witness_sample
from testsupport.ethos import REPLY, ethos_run, inquiry_run, run_ethos, scripted_judges
from testsupport.oidc import FakeOIDCClient
from testsupport.reports import pdf_text


@pytest.fixture
async def registry(db: AsyncSession) -> None:
    await sync_registry(db, load_registry(REPO_ROOT), "abc123")
    await db.commit()


@pytest.fixture
def witness() -> Iterator[WitnessConfig]:
    config = load_witness(REPO_ROOT / "config" / "witness.dev.yaml")
    app.dependency_overrides[get_witness] = lambda: config
    yield config
    app.dependency_overrides.pop(get_witness, None)


async def _samples(db: AsyncSession, run_id: str) -> list[RunSample]:
    return list((await db.execute(select(RunSample).where(RunSample.run_id == run_id))).scalars())


async def _launch(client: httpx.AsyncClient, source: dict) -> dict:
    response = await client.post(
        "/api/witness/runs", json={"source_run": source["id"], "reader": "lexicon-dev"}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_the_witness_reads_a_run_and_sits_beside_ethos(
    client: httpx.AsyncClient,
    idp: FakeOIDCClient,
    registry: None,
    db: AsyncSession,
    s3_server: str,
    witness: WitnessConfig,
    tmp_path: Path,
) -> None:
    source = await inquiry_run(client, idp, db)
    ethos = await ethos_run(client, source["id"])
    await run_ethos(db, ethos, scripted_judges)

    readers = (await client.get("/api/witness/readers")).json()
    assert [r["key"] for r in readers] == ["lexicon-dev"]
    run = await _launch(client, source)
    assert run["kind"] == "witness" and run["model_ids"] == {"witness": "agora/lexicon-dev"}
    assert run["prompt_sha"] == source["prompt_sha"] and run["seed_hash"] == source["seed_hash"]
    assert run["taxonomy_version"] == ethos["taxonomy_version"]
    assert run["config"]["reader_sha"] == witness.reader("lexicon-dev").sha256
    queues = (
        await db.execute(
            text("SELECT queue_name FROM procrastinate_jobs WHERE task_name = 'witness_sample'")
        )
    ).scalars()
    assert list(queues) == ["witness"]

    for sample in await _samples(db, run["id"]):
        await execute_witness_sample(sample.id, witness=witness)
    page = (await client.get(f"/api/witness/runs/{run['id']}")).json()
    assert page["run"]["status"] == "succeeded"
    assert page["samples"][0]["detail"] == {
        "runner_version": "lexicon-1",
        # Two probes on each of two replies (the mock tool call carries placeholder text),
        # and one note on the sentence that uses a reassurance word.
        "signals": 5,
        "dropped": {},
    }
    assert page["samples"][0]["tokens_used"] > 0

    reply = (await db.execute(select(Message).where(Message.content == REPLY))).scalar_one()
    assert page["ethos_run"]["id"] == ethos["id"]
    cells = {
        a["signal"]: {
            cell: [r["message_id"] for r in a[cell]]
            for cell in ("both", "ethos_only", "witness_only", "neither")
        }
        for a in page["agreements"]
    }
    mine = [str(reply.id)]
    # "promise" is on the reassurance list, and the panel found false reassurance.
    assert cells["reassurance_words"]["both"] == mine
    assert cells["reassurance_notes"]["both"] == mine
    # The panel found calibrated uncertainty; no word from the hedging list appears.
    assert cells["hedging_words"]["ethos_only"] == mine
    hedging = next(a for a in page["agreements"] if a["signal"] == "hedging_words")
    assert hedging["label"] == "calibrated_uncertainty" and hedging["replies"] == 2
    assert hedging["agreement"] == 0.5 and hedging["positive"] == 0

    signals = (
        await client.get(f"/api/witness/runs/{run['id']}/transcripts/{reply.transcript_id}")
    ).json()["signals"]
    signals = [s for s in signals if s["message_id"] == str(reply.id)]
    probe = next(s for s in signals if s["name"] == "reassurance_words")
    assert [REPLY[t["start"] : t["end"]] for t in probe["tokens"] if t["value"] >= 0.5] == [
        "promise"
    ]
    note = next(s for s in signals if s["kind"] == "nla")
    assert (
        REPLY[note["char_start"] : note["char_end"]] == "I can't promise the review will succeed."
    )
    assert "development reader" in note["explanation"].lower()

    report = await client.get(f"/api/record/runs/{run['id']}/report.pdf")
    assert report.status_code == 200
    printed = pdf_text(report.content, tmp_path)
    if printed is not None:
        assert "Signals beside Ethos labels" in printed
        assert "not the target model's internals" in printed

    # The run is finished, so its signals are read-only.
    with pytest.raises(DBAPIError, match="finished run"):
        await db.execute(
            text("UPDATE witness_signal SET explanation = 'edited' WHERE run_id = :run"),
            {"run": run["id"]},
        )
    await db.rollback()


async def test_changed_readers_and_runners_on_other_versions_fail_at_once(
    client: httpx.AsyncClient,
    idp: FakeOIDCClient,
    registry: None,
    db: AsyncSession,
    s3_server: str,
    witness: WitnessConfig,
) -> None:
    source = await inquiry_run(client, idp, db)

    run = await _launch(client, source)
    reader = witness.reader("lexicon-dev")
    moved = WitnessConfig(
        readers={"lexicon-dev": reader.model_copy(update={"version": "lexicon-2"})}
    )
    (sample,) = await _samples(db, run["id"])
    await execute_witness_sample(sample.id, witness=moved)
    await db.refresh(sample)
    assert sample.status == "failed" and "changed after launch" in (sample.error or "")

    run = await _launch(client, source)

    def elsewhere(config: ReaderConfig) -> LexiconRunner:
        assert config.lexicon is not None
        return LexiconRunner(lexicon=config.lexicon, version="lexicon-0")

    (sample,) = await _samples(db, run["id"])
    await execute_witness_sample(sample.id, witness=witness, runners=elsewhere)
    await db.refresh(sample)
    assert sample.status == "failed" and sample.attempts == 1
    assert "reports version 'lexicon-0'" in (sample.error or "")
    stored = (
        await db.execute(select(WitnessSignal).where(WitnessSignal.run_id == run["id"]))
    ).scalars()
    assert list(stored) == []


async def test_launching_checks_the_source_and_the_reader(
    client: httpx.AsyncClient,
    idp: FakeOIDCClient,
    registry: None,
    db: AsyncSession,
    s3_server: str,
    witness: WitnessConfig,
) -> None:
    source = await inquiry_run(client, idp, db)
    missing = await client.post(
        "/api/witness/runs", json={"source_run": source["id"], "reader": "nope"}
    )
    assert missing.status_code == 400 and "No witness reader" in missing.json()["detail"]
    nowhere = await client.post(
        "/api/witness/runs", json={"source_run": str(uuid.uuid4()), "reader": "lexicon-dev"}
    )
    assert nowhere.status_code == 404

    reader = witness.reader("lexicon-dev")
    unknown = reader.model_copy(
        update={"signals": [s.model_copy(update={"label": "mind_reading"}) for s in reader.signals]}
    )
    app.dependency_overrides[get_witness] = lambda: WitnessConfig(readers={"odd": unknown})
    refused = await client.post(
        "/api/witness/runs", json={"source_run": source["id"], "reader": "odd"}
    )
    assert refused.status_code == 400 and "mind_reading" in refused.json()["detail"]
