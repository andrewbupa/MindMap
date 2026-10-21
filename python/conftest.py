"""Shared test fixtures: a migrated test database and an in-process S3 server."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest

os.environ.setdefault("BENCH_ENVIRONMENT", "test")
os.environ.setdefault("BENCH_DATABASE_URL", "postgresql://bench:bench@localhost:5432/bench_test")
os.environ.setdefault("BENCH_SPACES_BUCKET", "bench-test")
os.environ.setdefault("BENCH_GIT_COMMIT", "0" * 40)
os.environ.setdefault("BENCH_BOOTSTRAP_ADMINS", "admin@example.test")

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

HERE = os.path.dirname(__file__)


@pytest.fixture(scope="session")
def migrated_database() -> Iterator[None]:
    config = Config(os.path.join(HERE, "alembic.ini"))
    config.set_main_option("script_location", "bench_core:migrations")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield


@pytest.fixture(scope="session")
def s3_server() -> Iterator[str]:
    from moto.server import ThreadedMotoServer

    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0)
    server.start()
    host, port = server.get_host_and_port()
    endpoint = f"http://{host}:{port}"
    os.environ["BENCH_SPACES_ENDPOINT"] = endpoint
    os.environ["BENCH_SPACES_KEY"] = "test"
    os.environ["BENCH_SPACES_SECRET"] = "test"
    from bench_core.config import get_settings
    from bench_core.storage import get_storage

    get_settings.cache_clear()
    get_storage.cache_clear()
    get_storage().ensure_bucket()
    yield endpoint
    server.stop()


TABLES_TO_CLEAR = (
    "review",
    "gold_label",
    "gold_item",
    "agreement",
    "gold_set",
    "annotation",
    "dropped_finding",
    "companion_signal",
    "score",
    "message",
    "transcript",
    "run_sample",
    "run",
    "expected_profile",
    "label",
    "taxonomy_version",
    "scenario",
    "persona",
    "behaviour",
    "tool_profile",
    "prompt_version",
    "agent",
    "data_import",
    "system_check",
    "user_session",
    "audit_event",
    '"user"',
    "procrastinate_jobs",
)


@pytest.fixture
async def db(migrated_database: None) -> AsyncIterator[AsyncSession]:
    """A session on a clean database. TRUNCATE does not fire the row-level guards."""
    from bench_core.db import get_sessionmaker

    async with get_sessionmaker()() as session:
        await session.execute(text(f"TRUNCATE {', '.join(TABLES_TO_CLEAR)} CASCADE"))
        await session.commit()
        yield session
        await session.rollback()
