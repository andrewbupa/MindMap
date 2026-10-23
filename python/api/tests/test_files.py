from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core.config import get_settings
from agora_core.storage import get_storage, sign_download
from testsupport.oidc import FakeOIDCClient, sign_in_as


async def test_a_signed_link_serves_its_file_to_a_signed_in_reader(
    client: httpx.AsyncClient, idp: FakeOIDCClient, db: AsyncSession
) -> None:
    storage = get_storage()
    await storage.aput_bytes("checks/one.json", b'{"ok":true}', "application/json")
    await storage.aput_bytes("runs/r/log.eval", b"PK\x03\x04", "application/zip")
    shown = storage.signed_url("checks/one.json")
    download = storage.signed_url("runs/r/log.eval", filename="log.eval")

    # Signed out, the link alone opens nothing.
    assert (await client.get(shown)).status_code == 401

    await sign_in_as(client, idp, "admin@example.test")
    json_file = await client.get(shown)
    assert json_file.status_code == 200 and json_file.json() == {"ok": True}
    assert json_file.headers["content-disposition"] == "inline"
    assert json_file.headers["cache-control"] == "private, no-store"

    log = await client.get(download)
    assert log.content == b"PK\x03\x04"
    assert log.headers["content-type"] == "application/zip"
    assert log.headers["content-disposition"] == 'attachment; filename="log.eval"'


async def test_an_expired_or_forged_link_opens_nothing(
    client: httpx.AsyncClient, idp: FakeOIDCClient, db: AsyncSession
) -> None:
    await get_storage().aput_bytes("checks/one.json", b"{}", "application/json")
    await sign_in_as(client, idp, "admin@example.test")
    secret = get_settings().session_secret.get_secret_value()
    expired = sign_download(secret, "checks/one.json", None, 300, now=0)
    forged = sign_download("not the secret", "checks/one.json", None, 300)
    missing = sign_download(secret, "checks/missing.json", None, 300)
    for token in (expired, forged, missing, "nonsense"):
        assert (await client.get(f"/api/files/{token}")).status_code == 404
