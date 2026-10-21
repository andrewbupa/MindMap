"""A round trip through queue, worker and storage, launched by an admin from Settings."""

from __future__ import annotations

import json
import logging
import socket
import uuid
from datetime import UTC, datetime

from procrastinate import RetryStrategy

from bench_core import audit
from bench_core.config import get_settings
from bench_core.db import session_scope
from bench_core.models import SystemCheck
from bench_core.provenance import current_git_commit, sha256_bytes
from bench_core.queue import app
from bench_core.storage import get_storage, object_key

log = logging.getLogger(__name__)


@app.task(name="system_check", retry=RetryStrategy(max_attempts=3, wait=5))
async def run_system_check(check_id: str) -> None:
    settings = get_settings()
    async with session_scope() as db:
        check = await db.get(SystemCheck, uuid.UUID(check_id))
        if check is None:
            log.warning("system check %s no longer exists", check_id)
            return
        check.status = "running"

    payload = {
        "check_id": check_id,
        "worker": socket.gethostname(),
        "commit": current_git_commit(settings.repo_root, settings.git_commit),
        "written_at": datetime.now(UTC).isoformat(),
    }
    data = json.dumps(payload, sort_keys=True).encode()
    key = object_key("system-checks", f"{check_id}.json")
    storage = get_storage()
    try:
        stored = await storage.aput_bytes(key, data, "application/json")
        read_back = await storage.aget_bytes(key)
    except Exception as error:
        async with session_scope() as db:
            check = await db.get(SystemCheck, uuid.UUID(check_id))
            if check is not None:
                check.status = "failed"
                check.detail = {"error": f"{type(error).__name__}: {error}"}
                check.finished_at = datetime.now(UTC)
        raise

    matches = read_back == data
    async with session_scope() as db:
        check = await db.get(SystemCheck, uuid.UUID(check_id))
        if check is None:
            return
        check.status = "succeeded" if matches else "failed"
        check.object_key = key
        check.detail = {
            **payload,
            "bucket": storage.bucket,
            "size": stored.size,
            "sha256": sha256_bytes(data),
            "read_back_matches": matches,
        }
        check.finished_at = datetime.now(UTC)
        await audit.record(
            db,
            "system_check.complete",
            actor_id=None,
            target_type="system_check",
            target_id=check.id,
            detail={"status": check.status, "key": key},
        )
