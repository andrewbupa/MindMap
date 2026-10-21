from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager

from bench_api import auth
from bench_api.main import app
from testsupport.oidc import FakeOAuth, FakeOIDCClient


@pytest.fixture
def idp(monkeypatch: pytest.MonkeyPatch) -> FakeOIDCClient:
    client = FakeOIDCClient()
    monkeypatch.setattr(auth, "get_oauth", lambda: FakeOAuth(client))
    return client


@pytest.fixture
async def client(db: Any) -> AsyncIterator[httpx.AsyncClient]:
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://bench.test", headers={"x-bench-request": "1"}
        ) as http:
            yield http
