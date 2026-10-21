"""A stand-in identity provider for API tests."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi.responses import RedirectResponse

ISSUER = "https://idp.example.test"


class FakeOIDCClient:
    """Stands in for the identity provider: returns whatever claims the test sets."""

    def __init__(self) -> None:
        self.claims: dict[str, Any] = {}

    async def authorize_redirect(self, request: Any, redirect_uri: str) -> RedirectResponse:
        request.session["state"] = "fake"
        return RedirectResponse(f"{ISSUER}/authorize?redirect_uri={redirect_uri}", status_code=302)

    async def authorize_access_token(self, request: Any) -> dict[str, Any]:
        return {"userinfo": self.claims, "id_token": "fake-id-token"}

    async def load_server_metadata(self) -> dict[str, Any]:
        return {"end_session_endpoint": f"{ISSUER}/logout"}


class FakeOAuth:
    def __init__(self, client: FakeOIDCClient) -> None:
        self.client = client

    def create_client(self, name: str) -> FakeOIDCClient:
        return self.client


async def sign_in_as(
    http: httpx.AsyncClient, idp: FakeOIDCClient, email: str, **claims: Any
) -> httpx.Response:
    idp.claims = {
        "iss": ISSUER,
        "sub": email,
        "email": email,
        "name": email.split("@")[0],
        **claims,
    }
    await http.get("/api/auth/login", params={"next": "/explore"})
    return await http.get("/api/auth/callback", params={"code": "x", "state": "fake"})
