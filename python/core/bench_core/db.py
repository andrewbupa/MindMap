"""Database connections.

App Platform gives the database URL as ``postgresql://...?sslmode=require`` and the
cluster's CA certificate as text. We write the certificate to a temporary file and
ask libpq to verify the server against it, then derive two forms of the URL: one
for SQLAlchemy (``postgresql+psycopg://``) and a plain libpq one for Procrastinate.
"""

from __future__ import annotations

import hashlib
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bench_core.config import Settings, get_settings


def _write_ca_cert(pem: str) -> Path:
    digest = hashlib.sha256(pem.encode()).hexdigest()[:16]
    path = Path(tempfile.gettempdir()) / f"bench-db-ca-{digest}.crt"
    if not path.exists():
        path.write_text(pem)
    return path


def libpq_url(settings: Settings) -> str:
    """The database URL in the form libpq and Procrastinate expect."""
    parts = urlsplit(settings.database_url)
    scheme = "postgresql"
    query = dict(parse_qsl(parts.query))
    if settings.database_ca_cert is not None:
        pem = settings.database_ca_cert.get_secret_value().strip()
        if pem:
            query["sslrootcert"] = str(_write_ca_cert(pem + "\n"))
            query["sslmode"] = "verify-full"
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def sqlalchemy_url(settings: Settings) -> str:
    """The database URL with SQLAlchemy's psycopg 3 driver selected."""
    url = libpq_url(settings)
    return "postgresql+psycopg://" + url.split("://", 1)[1]


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(
        sqlalchemy_url(get_settings()),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """A session that commits on success and rolls back on error."""
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise
