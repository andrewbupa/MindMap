"""Operational commands that run inside the Python image.

python -m bench_worker.cli ensure-bucket   create the storage bucket (local only)
python -m bench_worker.cli seed-demo       load synthetic demo data
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time

from botocore.exceptions import BotoCoreError, ClientError

from bench_core.config import Environment, get_settings
from bench_core.storage import get_storage

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


async def seed_demo() -> None:
    # Milestone 2 adds agents, prompt versions, tool profiles and personas here.
    ensure_bucket()
    print("demo data: nothing further to load in milestone 1")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(prog="bench")
    parser.add_argument("command", choices=["ensure-bucket", "seed-demo"])
    args = parser.parse_args()
    if args.command == "ensure-bucket":
        ensure_bucket()
    else:
        asyncio.run(seed_demo())


if __name__ == "__main__":
    main()
