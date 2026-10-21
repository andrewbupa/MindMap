"""Alembic environment. Runs synchronously with psycopg 3 against BENCH_DATABASE_URL."""

from __future__ import annotations

from typing import Any

from alembic import context
from sqlalchemy import create_engine, pool

from bench_core.config import get_settings
from bench_core.db import sqlalchemy_url
from bench_core.models import Base

target_metadata = Base.metadata


def include_object(
    obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
) -> bool:
    # Procrastinate owns its own tables; our revisions apply its SQL verbatim.
    return not (type_ == "table" and name is not None and name.startswith("procrastinate_"))


def run_migrations_offline() -> None:
    context.configure(
        url=sqlalchemy_url(get_settings()),
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(sqlalchemy_url(get_settings()), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
