"""Where Agora keeps files: Inspect logs, the judges' raw answers and system checks.

Containers on App Platform have temporary disks, so files go to Postgres (the
default, table ``stored_file``) or to DigitalOcean Spaces. Either way nothing is
public. Spaces signs its own short-lived URLs; for Postgres the API signs a link to
``/api/files/<token>`` and serves the file to a signed-in reader.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from sqlalchemy.dialects.postgresql import insert

from agora_core.config import Settings, StorageKind, get_settings
from agora_core.db import session_scope
from agora_core.models import StoredFile

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


class StorageError(RuntimeError):
    pass


def object_key(*segments: str) -> str:
    """Join key segments, refusing anything that could escape its prefix."""
    for segment in segments:
        if not _SAFE_SEGMENT.match(segment) or ".." in segment:
            raise StorageError(f"unsafe object key segment: {segment!r}")
    return "/".join(segments)


def run_prefix(run_id: str) -> str:
    return object_key("runs", run_id)


@dataclass(frozen=True)
class StoredObject:
    key: str
    size: int
    etag: str


class Storage(Protocol):
    """What the rest of Agora needs from a store."""

    name: str
    signed_url_seconds: int

    def uri(self, key: str) -> str:
        """How a run or transcript records where its file is."""
        ...

    def signed_url(self, key: str, filename: str | None = None) -> str:
        """A short-lived link a browser can open; with a filename, a download."""
        ...

    def ensure_ready(self) -> None:
        """Make the store usable, where that needs doing (a bucket, locally)."""
        ...

    async def aput_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject: ...

    async def aget_bytes(self, key: str) -> bytes: ...

    async def aput_file(self, key: str, path: Path, content_type: str) -> StoredObject: ...


class SpacesStorage:
    """DigitalOcean Spaces, or any S3-compatible store."""

    name = "spaces"

    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.spaces_bucket
        self.region = settings.spaces_region
        self.signed_url_seconds = settings.signed_url_seconds
        self._client = _client(settings, settings.spaces_endpoint)
        # Signed URLs are opened by browsers, which may reach storage by another
        # name than our containers do (locally, localhost rather than s3).
        public = settings.spaces_public_endpoint or settings.spaces_endpoint
        self._signer = (
            self._client if public == settings.spaces_endpoint else _client(settings, public)
        )

    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject:
        response = self._client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type, ACL="private"
        )
        return StoredObject(key=key, size=len(data), etag=response["ETag"].strip('"'))

    def put_file(self, key: str, path: Path, content_type: str) -> StoredObject:
        self._client.upload_file(
            str(path),
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type, "ACL": "private"},
        )
        head = self._client.head_object(Bucket=self.bucket, Key=key)
        return StoredObject(key=key, size=head["ContentLength"], etag=head["ETag"].strip('"'))

    def get_bytes(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as error:
            raise StorageError(f"could not read {key}: {error}") from error
        return response["Body"].read()

    def download(self, key: str, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._client.download_file(self.bucket, key, str(path))
        return path

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return True

    def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(item["Key"] for item in page.get("Contents", []))
        return keys

    def signed_url(self, key: str, filename: str | None = None) -> str:
        params: dict[str, str] = {"Bucket": self.bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        return self._signer.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=self.signed_url_seconds
        )

    def uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"

    def ensure_ready(self) -> None:
        self.ensure_bucket()

    def ensure_bucket(self) -> None:
        """Create the bucket if missing. Used locally; in production it is made by hand."""
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError:
            if self.region == "us-east-1":
                self._client.create_bucket(Bucket=self.bucket)
            else:
                self._client.create_bucket(
                    Bucket=self.bucket,
                    CreateBucketConfiguration={"LocationConstraint": self.region},  # type: ignore[typeddict-item]
                )

    async def aput_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject:
        return await asyncio.to_thread(self.put_bytes, key, data, content_type)

    async def aget_bytes(self, key: str) -> bytes:
        return await asyncio.to_thread(self.get_bytes, key)

    async def aput_file(self, key: str, path: Path, content_type: str) -> StoredObject:
        return await asyncio.to_thread(self.put_file, key, path, content_type)


def _client(settings: Settings, endpoint: str) -> S3Client:
    spaces = endpoint.rstrip("/").endswith("digitaloceanspaces.com")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=settings.spaces_region,
        aws_access_key_id=settings.spaces_key.get_secret_value(),
        aws_secret_access_key=settings.spaces_secret.get_secret_value(),
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual" if spaces else "path"},
            retries={"max_attempts": 5, "mode": "standard"},
        ),
    )


# Signed download links for files kept in Postgres.
_SALT = b"agora.download."
_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign_download(
    secret: str, key: str, filename: str | None, seconds: int, now: float | None = None
) -> str:
    """A token naming one file, valid for ``seconds``, signed with the session secret."""
    if filename is not None and not _FILENAME.match(filename):
        raise StorageError(f"unsafe filename: {filename!r}")
    expires = int((now if now is not None else time.time()) + seconds)
    body = _b64(json.dumps({"k": key, "f": filename, "e": expires}, separators=(",", ":")).encode())
    mac = hmac.new(secret.encode(), _SALT + body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64(mac)}"


def read_download(secret: str, token: str, now: float | None = None) -> tuple[str, str | None]:
    """The key and filename a token names, if its signature holds and it has not expired."""
    try:
        body, mac = token.split(".")
        expected = hmac.new(secret.encode(), _SALT + body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(mac)):
            raise StorageError("bad signature")
        claims = json.loads(_unb64(body))
    except (ValueError, TypeError) as error:
        raise StorageError("malformed download token") from error
    if int(claims["e"]) < (now if now is not None else time.time()):
        raise StorageError("expired download token")
    return str(claims["k"]), claims["f"]


class DatabaseStorage:
    """Files in Postgres, one row each, under the keys Spaces would use. Writing a key
    again replaces it, as in a bucket."""

    name = "database"

    def __init__(self, settings: Settings) -> None:
        self.signed_url_seconds = settings.signed_url_seconds
        self._secret = settings.session_secret.get_secret_value()

    def uri(self, key: str) -> str:
        return f"db://stored_file/{key}"

    def signed_url(self, key: str, filename: str | None = None) -> str:
        return f"/api/files/{sign_download(self._secret, key, filename, self.signed_url_seconds)}"

    def ensure_ready(self) -> None:
        """Nothing to do: migrations create the table."""

    async def aput_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject:
        digest = hashlib.sha256(data).hexdigest()
        row = {"key": key, "content_type": content_type, "size": len(data), "sha256": digest}
        statement = insert(StoredFile).values(data=data, **row)
        statement = statement.on_conflict_do_update(
            index_elements=[StoredFile.key], set_={"data": statement.excluded.data, **row}
        )
        async with session_scope() as db:
            await db.execute(statement)
        return StoredObject(key=key, size=len(data), etag=digest)

    async def aread(self, key: str) -> tuple[bytes, str]:
        """A file and its content type."""
        async with session_scope() as db:
            found = await db.get(StoredFile, key)
            if found is None:
                raise StorageError(f"could not read {key}: no such file")
            return found.data, found.content_type

    async def aget_bytes(self, key: str) -> bytes:
        return (await self.aread(key))[0]

    async def aput_file(self, key: str, path: Path, content_type: str) -> StoredObject:
        return await self.aput_bytes(key, await asyncio.to_thread(path.read_bytes), content_type)


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage is StorageKind.spaces:
        return SpacesStorage(settings)
    return DatabaseStorage(settings)
