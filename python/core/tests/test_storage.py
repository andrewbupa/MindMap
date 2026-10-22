import pytest

from agora_core.storage import StorageError, get_storage, object_key, run_prefix


def test_object_key_joins_safe_segments() -> None:
    assert object_key("runs", "abc", "log.eval") == "runs/abc/log.eval"
    assert run_prefix("1234") == "runs/1234"


@pytest.mark.parametrize("segment", ["..", "a/b", "", ".hidden", "a..b", "x" * 201])
def test_object_key_refuses_unsafe_segments(segment: str) -> None:
    with pytest.raises(StorageError):
        object_key("runs", segment)


def test_round_trip_and_signed_url(s3_server: str) -> None:
    storage = get_storage()
    stored = storage.put_bytes("checks/one.json", b'{"ok":true}', "application/json")
    assert stored.size == 11
    assert storage.exists("checks/one.json")
    assert not storage.exists("checks/missing.json")
    assert storage.get_bytes("checks/one.json") == b'{"ok":true}'
    assert "checks/one.json" in storage.list_keys("checks/")
    url = storage.signed_url("checks/one.json", filename="one.json")
    assert "X-Amz-Signature=" in url and "X-Amz-Expires=300" in url


def test_signed_urls_can_use_a_public_endpoint(s3_server: str) -> None:
    from agora_core.config import Settings
    from agora_core.storage import Storage

    settings = Settings(spaces_endpoint=s3_server, spaces_public_endpoint="http://localhost:8333")
    url = Storage(settings).signed_url("checks/one.json")
    assert url.startswith("http://localhost:8333/agora-test/checks/one.json?")
