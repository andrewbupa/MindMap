"""Procrastinate 3.10.0 queue schema

Procrastinate has no Alembic integration, so we vendor its SQL and apply it here.
When upgrading Procrastinate, add a revision that applies each newer file from
``procrastinate/sql/migrations`` in order (``pre`` files before the code deploy,
``post`` files after). See docs/DECISIONS.md.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-21 12:05:00
"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = Path(__file__).resolve().parents[1] / "sql" / "procrastinate_3.10.0_schema.sql"


def upgrade() -> None:
    op.execute(SCHEMA.read_text())


def downgrade() -> None:
    # Drop every object Procrastinate created: tables, functions and types.
    op.execute(
        """
        DO $$
        DECLARE
            item record;
        BEGIN
            FOR item IN
                SELECT tablename FROM pg_tables
                WHERE schemaname = current_schema() AND tablename LIKE 'procrastinate%'
            LOOP
                EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', item.tablename);
            END LOOP;
            FOR item IN
                SELECT p.oid::regprocedure AS signature FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = current_schema() AND p.proname LIKE 'procrastinate%'
            LOOP
                EXECUTE format('DROP ROUTINE IF EXISTS %s CASCADE', item.signature);
            END LOOP;
            FOR item IN
                SELECT t.typname FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE n.nspname = current_schema() AND t.typname LIKE 'procrastinate%'
                  AND t.typtype IN ('e', 'c')
            LOOP
                EXECUTE format('DROP TYPE IF EXISTS %I CASCADE', item.typname);
            END LOOP;
        END;
        $$;
        """
    )
