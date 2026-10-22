from __future__ import annotations

import csv
import io
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core.config import REPO_ROOT
from agora_core.models import AuditEvent, User
from agora_core.registry import load_registry, sync_registry
from testsupport.ethos import ethos_run, inquiry_run, run_ethos, scripted_judges
from testsupport.oidc import FakeOIDCClient, sign_in_as
from testsupport.reports import pdf_text


@pytest.fixture
async def registry(db: AsyncSession) -> None:
    await sync_registry(db, load_registry(REPO_ROOT), "abc123")
    await db.commit()


async def test_ethos_disagreements_reach_the_review_queue(
    client: httpx.AsyncClient,
    idp: FakeOIDCClient,
    registry: None,
    db: AsyncSession,
    s3_server: str,
) -> None:
    source = await inquiry_run(client, idp, db)
    run = await ethos_run(client, source["id"])
    await run_ethos(db, run, scripted_judges)
    await sign_in_as(client, idp, "rev@example.test")
    await db.execute(
        update(User).where(User.email == "rev@example.test").values(roles=["reviewer"])
    )
    await db.commit()

    queue = (await client.get("/api/jury/ethos-queue")).json()
    (item,) = queue["items"]
    assert item["label"] == "false_reassurance" and item["median"] == 1.5
    assert item["by_judge"] == {"anthropic/claude-opus-5-5": 3, "openai/gpt-6.1-sol": 0}
    assert [a["quote"] for a in item["annotations"]] == ["Here is what was decided."]

    verdict = await client.post(
        "/api/jury",
        json={
            "annotation_id": item["annotations"][0]["id"],
            "verdict": "disagree",
            "corrected_intensity": 0,
            "notes": "A plain statement of the decision, not reassurance.",
        },
    )
    assert verdict.status_code == 201, verdict.text
    assert (await client.get("/api/jury/ethos-queue")).json()["items"] == []


async def test_reports_export_pdf_and_findings_with_provenance(
    client: httpx.AsyncClient,
    idp: FakeOIDCClient,
    registry: None,
    db: AsyncSession,
    s3_server: str,
    tmp_path: Path,
) -> None:
    source = await inquiry_run(client, idp, db)
    run = await ethos_run(client, source["id"])
    await run_ethos(db, run, scripted_judges)

    listed = {r["id"] for r in (await client.get("/api/record/runs")).json()}
    assert {source["id"], run["id"]} <= listed

    for target in (source, run):
        response = await client.get(f"/api/record/runs/{target['id']}/report.pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF")
        text = pdf_text(response.content, tmp_path)
        if text is not None:
            assert "Provenance" in text and target["config_hash"] in text
            assert (target["seed_hash"] or "") in text
    if text := pdf_text(
        (await client.get(f"/api/record/runs/{run['id']}/report.pdf")).content, tmp_path
    ):
        assert "Labels across every reply" in text and "calibrated uncertainty" in text

    findings = await client.get(f"/api/record/runs/{run['id']}/findings.csv")
    rows = list(csv.DictReader(io.StringIO(findings.text)))
    assert len(rows) == 4
    assert {r["taxonomy_version"] for r in rows} == {"2026.10.1"}
    assert {r["run_id"] for r in rows} == {run["id"]}
    assert "Here is what was decided." in {r["quote"] for r in rows}
    missing = await client.get(f"/api/record/runs/{source['id']}/findings.csv")
    assert missing.status_code == 404

    exports = (
        (await db.execute(select(AuditEvent).where(AuditEvent.action == "report.export")))
        .scalars()
        .all()
    )
    assert {e.detail["format"] for e in exports} == {"pdf", "csv-findings"}
