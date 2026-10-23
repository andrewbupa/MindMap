import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agora_core.config import Settings, StorageKind, get_settings
from agora_core.storage import (
    DatabaseStorage,
    SpacesStorage,
    StorageError,
    get_storage,
    object_key,
    read_download,
    run_prefix,
    sign_download,
)


def test_object_key_joins_safe_segments() -> None:
    assert object_key("runs", "abc", "log.eval") == "runs/abc/log.eval"
    assert run_prefix("1234") == "runs/1234"


@pytest.mark.parametrize("segment", ["..", "a/b", "", ".hidden", "a..b", "x" * 201])
def test_object_key_refuses_unsafe_segments(segment: str) -> None:
    with pytest.raises(StorageError):
        object_key("runs", segment)


def test_files_go_to_postgres_unless_spaces_is_asked_for() -> None:
    assert get_settings().storage is StorageKind.database
    assert isinstance(get_storage(), DatabaseStorage)


async def test_postgres_keeps_files_and_replaces_a_key_written_again(db: AsyncSession) -> None:
    storage = DatabaseStorage(get_settings())
    stored = await storage.aput_bytes("checks/one.json", b'{"ok":true}', "application/json")
    assert stored.size == 11 and len(stored.etag) == 64
    assert await storage.aread("checks/one.json") == (b'{"ok":true}', "application/json")
    await storage.aput_bytes("checks/one.json", b"{}", "application/json")
    assert await storage.aget_bytes("checks/one.json") == b"{}"
    assert storage.uri("checks/one.json") == "db://stored_file/checks/one.json"
    with pytest.raises(StorageError):
        await storage.aget_bytes("checks/missing.json")


def test_download_links_name_one_file_and_expire() -> None:
    token = sign_download("secret", "runs/a/b.eval", "b.eval", 300, now=1000)
    assert read_download("secret", token, now=1299) == ("runs/a/b.eval", "b.eval")
    with pytest.raises(StorageError, match="expired"):
        read_download("secret", token, now=1301)
    with pytest.raises(StorageError):
        read_download("another secret", token, now=1000)
    body, mac = token.split(".")
    with pytest.raises(StorageError):
        read_download("secret", f"{body}x.{mac}", now=1000)
    with pytest.raises(StorageError):
        read_download("secret", "not-a-token", now=1000)
    with pytest.raises(StorageError):
        sign_download("secret", "runs/a/b.eval", 'b".eval', 300)


def test_spaces_round_trip_and_signed_url(s3_server: str) -> None:
    storage = SpacesStorage(get_settings())
    stored = storage.put_bytes("checks/one.json", b'{"ok":true}', "application/json")
    assert stored.size == 11
    assert storage.exists("checks/one.json")
    assert not storage.exists("checks/missing.json")
    assert storage.get_bytes("checks/one.json") == b'{"ok":true}'
    assert "checks/one.json" in storage.list_keys("checks/")
    assert storage.uri("checks/one.json") == "s3://agora-test/checks/one.json"
    url = storage.signed_url("checks/one.json", filename="one.json")
    assert "X-Amz-Signature=" in url and "X-Amz-Expires=300" in url


def test_spaces_signed_urls_can_use_a_public_endpoint(s3_server: str) -> None:
    settings = Settings(
        storage=StorageKind.spaces,
        spaces_endpoint=s3_server,
        spaces_public_endpoint="http://localhost:8333",
    )
    url = SpacesStorage(settings).signed_url("checks/one.json")
    assert url.startswith("http://localhost:8333/agora-test/checks/one.json?")
