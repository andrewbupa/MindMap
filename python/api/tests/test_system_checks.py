from __future__ import annotations

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import FakeOIDCClient, sign_in_as


async def test_admin_launches_a_check_that_queues_a_job(
    client: httpx.AsyncClient, idp: FakeOIDCClient, db: AsyncSession
) -> None:
    await sign_in_as(client, idp, "admin@example.test")
    response = await client.post("/api/system/checks")
    assert response.status_code == 201
    check = response.json()
    assert check["status"] == "queued" and check["job_id"]

    job = (
        await db.execute(
            text("SELECT task_name, args FROM procrastinate_jobs WHERE id = :id"),
            {"id": check["job_id"]},
        )
    ).one()
    assert job.task_name == "system_check"
    assert job.args == {"check_id": check["id"]}

    listed = (await client.get("/api/system/checks")).json()
    assert [item["id"] for item in listed] == [check["id"]]
    assert (await client.get(f"/api/system/checks/{check['id']}/object")).status_code == 404


async def test_only_admins_launch_checks(client: httpx.AsyncClient, idp: FakeOIDCClient) -> None:
    await sign_in_as(client, idp, "author@example.test")
    assert (await client.post("/api/system/checks")).status_code == 403


async def test_health_and_readiness(client: httpx.AsyncClient) -> None:
    health = (await client.get("/api/health")).json()
    assert health["status"] == "ok" and health["environment"] == "test"
    ready = await client.get("/api/health/ready")
    assert ready.status_code == 200 and ready.json() == {
        "status": "ok",
        "database": True,
        "queue": True,
    }
