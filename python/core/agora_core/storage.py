"""Object storage on DigitalOcean Spaces, or any S3-compatible store.

Containers on App Platform have temporary disks. Anything worth keeping is written
to a temporary path, uploaded here, and served back through short-lived signed URLs.
The bucket is private: there are no public objects.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from agora_core.config import Settings, get_settings

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

    def uri(self, bucket: str) -> str:
        return f"s3://{bucket}/{self.key}"


class Storage:
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


@lru_cache
def get_storage() -> Storage:
    return Storage(get_settings())
