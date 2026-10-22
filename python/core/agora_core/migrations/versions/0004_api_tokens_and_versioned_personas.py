"""api tokens and versioned personas

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-21 12:09:09.174351
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

IMMUTABLE = ("prompt_version", "tool_profile", "persona", "scenario", "behaviour")


def upgrade() -> None:
    op.create_table(
        "api_token",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=12), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["user.id"], name=op.f("fk_api_token_created_by_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_token")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_api_token_token_hash")),
    )
    op.drop_constraint(op.f("uq_persona_agent_id_key"), "persona", type_="unique")
    op.create_unique_constraint(
        op.f("uq_persona_agent_id_key_sha256"), "persona", ["agent_id", "key", "sha256"]
    )
    # What a run tested must never change underneath it: these rows are write-once.
    for table in IMMUTABLE:
        op.execute(
            f"""
            CREATE TRIGGER {table}_write_once
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION agora_refuse_change();
            """
        )


def downgrade() -> None:
    for table in IMMUTABLE:
        op.execute(f"DROP TRIGGER {table}_write_once ON {table}")
    op.drop_constraint(op.f("uq_persona_agent_id_key_sha256"), "persona", type_="unique")
    op.create_unique_constraint(
        op.f("uq_persona_agent_id_key"),
        "persona",
        ["agent_id", "key"],
        postgresql_nulls_not_distinct=False,
    )
    op.drop_table("api_token")
