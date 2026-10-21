"""Operational commands that run inside the Python image.

python -m bench_worker.cli migrate          apply migrations, then sync the registry (pre-deploy)
python -m bench_worker.cli sync-registry    load agents/ and the Lens taxonomy into Postgres
python -m bench_worker.cli scan-synthetic   check agents/, seeds/ and config/ for personal data
python -m bench_worker.cli ensure-bucket    create the storage bucket (local only)
python -m bench_worker.cli seed-demo        all three, for local development
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time

from alembic import command as alembic
from alembic.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from bench_core.config import Environment, get_settings
from bench_core.db import session_scope
from bench_core.lens.taxonomy import load_lens, sync_lens
from bench_core.provenance import current_git_commit
from bench_core.registry import load_registry, sync_registry
from bench_core.storage import get_storage
from bench_core.synthetic import scan_tree

log = logging.getLogger("bench_worker.cli")


def ensure_bucket() -> None:
    settings = get_settings()
    if settings.environment is Environment.production:
        raise SystemExit("In production the Spaces bucket is created by hand; see docs/RUNBOOK.md.")
    # Local storage servers can take a few seconds to accept connections.
    for attempt in range(30):
        try:
            get_storage().ensure_bucket()
            break
        except (BotoCoreError, ClientError) as error:
            if attempt == 29:
                raise
            log.info("storage not ready yet (%s); retrying", type(error).__name__)
            time.sleep(2)
    print(f"bucket {settings.spaces_bucket} is ready")


def scan_synthetic() -> None:
    findings = scan_tree(get_settings().repo_root, ["agents", "seeds", "config"])
    for finding in findings:
        print(finding.describe())
    if findings:
        raise SystemExit(f"{len(findings)} possible personal data findings; see above")
    print("no personal data found in agents/, seeds/ or config/")


async def sync() -> None:
    settings = get_settings()
    registry = load_registry(settings.repo_root)
    commit = current_git_commit(settings.repo_root, settings.git_commit)
    lens = load_lens(settings.repo_root)
    async with session_scope() as db:
        report = await sync_registry(db, registry, commit)
        await sync_lens(db, lens, commit)
    for label, items in (
        ("agents", report.agents_added),
        ("prompt versions", report.prompts_added),
        ("tool profiles", report.tool_profiles_added),
        ("personas", report.personas_added),
    ):
        if items:
            print(f"added {label}: {', '.join(items)}")
    if not report.changed:
        print("registry is up to date")
    print(f"Lens taxonomy {lens.taxonomy.version} is loaded")


def migrate() -> None:
    """The pre-deploy job: the schema first, then what git says we test."""
    settings = get_settings()
    alembic.upgrade(Config(str(settings.repo_root / "python" / "alembic.ini")), "head")
    asyncio.run(sync())


async def seed_demo() -> None:
    scan_synthetic()
    ensure_bucket()
    await sync()


COMMANDS = ("migrate", "sync-registry", "scan-synthetic", "ensure-bucket", "seed-demo")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(prog="bench")
    parser.add_argument("command", choices=COMMANDS)
    command = parser.parse_args().command
    if command == "migrate":
        migrate()
    elif command == "ensure-bucket":
        ensure_bucket()
    elif command == "scan-synthetic":
        scan_synthetic()
    elif command == "sync-registry":
        asyncio.run(sync())
    else:
        asyncio.run(seed_demo())


if __name__ == "__main__":
    main()
