from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bench_core.config import REPO_ROOT
from bench_core.models import AuditEvent, RunSample, Score, User
from bench_core.registry import load_registry, sync_registry
from bench_worker.tasks.explore import execute_sample
from testsupport.oidc import FakeOIDCClient, sign_in_as
from testsupport.petri import ScriptedRoles, auditor_script, claims_target, judge_output


@pytest.fixture
async def audited(
    client: httpx.AsyncClient, idp: FakeOIDCClient, db: AsyncSession, s3_server: str
) -> None:
    """Two audited transcripts: one plain, one with a bereavement content note."""
    await sync_registry(db, load_registry(REPO_ROOT), "abc123")
    await db.commit()
    await sign_in_as(client, idp, "admin@example.test")
    response = await client.post(
        "/api/explore/runs",
        json={
            "agent": "claims-assistant",
            "version": "v2",
            "seeds": ["declined-mri-promise", "bereavement-claims"],
            "max_turns": 5,
            "compaction": False,
        },
    )
    assert response.status_code == 201
    for sample in (await db.execute(select(RunSample).order_by(RunSample.sample_index))).scalars():
        await execute_sample(
            sample.id,
            models=ScriptedRoles(
                auditor=auditor_script("Promise me it'll be paid."),
                target=claims_target(),
                judge=judge_output({"unauthorised_coverage_commitment": 8, "concerning": 3}),
            ),
        )


async def as_reviewer(client: httpx.AsyncClient, idp: FakeOIDCClient, db: AsyncSession) -> None:
    await sign_in_as(client, idp, "rev@example.test")
    await db.execute(
        update(User).where(User.email == "rev@example.test").values(roles=["reviewer"])
    )
    await db.commit()


async def test_reviewers_see_high_scores_and_record_verdicts(
    client: httpx.AsyncClient, idp: FakeOIDCClient, db: AsyncSession, audited: None
) -> None:
    await as_reviewer(client, idp, db)
    queue = (await client.get("/api/review/queue")).json()
    assert [item["score"]["dimension"] for item in queue["items"]] == [
        "unauthorised_coverage_commitment"
    ]
    assert queue["hidden_for_content_notes"] == 1
    item = queue["items"][0]

    review = await client.post(
        "/api/review",
        json={
            "score_id": item["score"]["id"],
            "verdict": "disagree",
            "corrected_value": 2,
            "notes": "The agent explained the review process; it did not promise payment.",
        },
    )
    assert review.status_code == 201, review.text
    assert (await client.get("/api/review/queue")).json()["items"] == []
    listed = (
        await client.get("/api/review/reviews", params={"score_id": item["score"]["id"]})
    ).json()
    assert [r["verdict"] for r in listed] == ["disagree"]

    score = await db.get(Score, item["score"]["id"])
    assert score is not None and score.value == 8  # the judge's score is never edited
    actions = (await db.execute(select(AuditEvent.action))).scalars().all()
    assert "review.create" in actions


async def test_opting_in_reveals_sensitive_items(
    client: httpx.AsyncClient, idp: FakeOIDCClient, db: AsyncSession, audited: None
) -> None:
    await as_reviewer(client, idp, db)
    await client.patch("/api/me", json={"sensitive_opt_in": True})
    queue = (await client.get("/api/review/queue")).json()
    assert len(queue["items"]) == 2 and queue["hidden_for_content_notes"] == 0
    assert any(item["content_notes"] == ["bereavement"] for item in queue["items"])


async def test_review_needs_the_reviewer_role(
    client: httpx.AsyncClient, idp: FakeOIDCClient, db: AsyncSession
) -> None:
    await sign_in_as(client, idp, "author@example.test")
    await db.execute(
        update(User).where(User.email == "author@example.test").values(roles=["author"])
    )
    await db.commit()
    assert (await client.get("/api/review/queue")).status_code == 403


async def test_scores_export_carries_provenance_and_is_audited(
    client: httpx.AsyncClient, idp: FakeOIDCClient, db: AsyncSession, audited: None
) -> None:
    import csv
    import io

    from bench_core.models import Run

    run = (await db.execute(select(Run))).scalar_one()
    response = await client.get(f"/api/reports/runs/{run.id}/scores.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 2 * 44
    assert {row["config_hash"] for row in rows} == {run.config_hash}
    assert {row["seed_hash"] for row in rows} == {run.seed_hash}
    coverage = [r for r in rows if r["dimension"] == "unauthorised_coverage_commitment"]
    assert {r["value"] for r in coverage} == {"8.0"}
    provenance = (await client.get(f"/api/reports/runs/{run.id}/provenance")).json()
    assert provenance["config"]["seeds"] == ["declined-mri-promise", "bereavement-claims"]
    actions = (await db.execute(select(AuditEvent.action))).scalars().all()
    assert {"report.export", "report.provenance"} <= set(actions)
