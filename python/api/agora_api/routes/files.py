"""Files kept in Postgres, served through the short-lived links that storage signs.

A link names one file and lasts a few minutes, like a Spaces signed URL, and only a
signed-in reader can open it. Agora wrote every file itself; even so, a file is only
ever shown inline as JSON, and anything else downloads.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from agora_api.deps import AppSettings, ReaderUser
from agora_core.storage import DatabaseStorage, StorageError, get_storage, read_download

router = APIRouter(prefix="/files", tags=["files"])

INLINE = {"application/json"}


@router.get("/{token}", response_class=Response)
async def read_file(token: str, _: ReaderUser, settings: AppSettings) -> Response:
    storage = get_storage()
    try:
        if not isinstance(storage, DatabaseStorage):
            raise StorageError("files are not kept in Postgres")
        key, filename = read_download(settings.session_secret.get_secret_value(), token)
        data, content_type = await storage.aread(key)
    except StorageError as error:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "This link has expired or names no file. Open it again from Agora.",
        ) from error
    disposition = "inline" if content_type in INLINE and not filename else "attachment"
    if filename:
        disposition += f'; filename="{filename}"'
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": disposition,
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "X-Content-Type-Options": "nosniff",
        },
    )
