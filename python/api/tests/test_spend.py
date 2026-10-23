from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core.models import Run
from testsupport.oidc import FakeOIDCClient, sign_in_as

SYDNEY = ZoneInfo("Australia/Sydney")


def _run(kind: str, at: datetime, tokens: int, cost: str) -> Run:
    return Run(
        kind=kind,
        title=f"{kind} at {at.isoformat()}",
        config={},
        config_hash="0" * 64,
        git_commit="abc",
        model_ids={},
        token_budget=1_000_000,
        tokens_used=tokens,
        cost_usd=Decimal(cost),
        created_at=at,
    )


async def test_spend_is_counted_by_the_month_runs_started_in_sydney(
    client: httpx.AsyncClient, idp: FakeOIDCClient, db: AsyncSession
) -> None:
    now = datetime.now(UTC).astimezone(SYDNEY)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month = f"{now.year:04d}-{now.month:02d}"
    before = month_start - timedelta(minutes=1)
    last_month = f"{before.year:04d}-{before.month:02d}"
    db.add_all(
        [
            # A minute into the month in Sydney is still the month before in UTC.
            _run("inquiry", month_start + timedelta(minutes=1), 1000, "1.50"),
            _run("tally", month_start + timedelta(minutes=2), 3000, "2.25"),
            _run("inquiry", before, 500, "0.75"),
        ]
    )
    await db.commit()

    await sign_in_as(client, idp, "admin@example.test")
    spend = (await client.get("/api/runs/spend", params={"months": 3})).json()
    assert spend["time_zone"] == "Australia/Sydney"
    assert len(spend["months"]) == 3
    current, previous, empty = spend["months"]
    assert current["month"] == this_month and previous["month"] == last_month
    assert (current["runs"], current["tokens"], current["cost_usd"]) == (2, 4000, 3.75)
    assert current["by_kind"]["tally"] == {"runs": 1, "tokens": 3000, "cost_usd": 2.25}
    assert (previous["runs"], previous["cost_usd"]) == (1, 0.75)
    assert empty["runs"] == 0 and empty["by_kind"] == {}
    # Judge B's model has no price yet, so its tokens count as nothing; the page says so.
    assert "openai/gpt-6.1-sol" in spend["unpriced_models"]

    listed = (await client.get("/api/record/runs", params={"month": this_month})).json()
    assert sorted(run["kind"] for run in listed) == ["inquiry", "tally"]
    assert (await client.get("/api/record/runs", params={"month": "2026-13"})).status_code == 422
