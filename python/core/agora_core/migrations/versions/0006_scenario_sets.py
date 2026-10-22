"""scenario sets: Bloom scenario generation runs and their write-once output

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-21 16:08:56.743704
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = "'explore', 'measure', 'lens', 'playground'"


def upgrade() -> None:
    op.drop_constraint("known_kind", "run", type_="check")
    op.create_check_constraint("known_kind", "run", f"kind IN ({KINDS}, 'scenarios')")
    op.create_table(
        "scenario_set",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("behaviour_id", sa.UUID(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("presence_dimension", sa.String(length=100), nullable=False),
        sa.Column("scenario_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["behaviour_id"], ["behaviour.id"], name=op.f("fk_scenario_set_behaviour_id_behaviour")
        ),
        sa.ForeignKeyConstraint(["run_id"], ["run.id"], name=op.f("fk_scenario_set_run_id_run")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenario_set")),
        sa.UniqueConstraint("run_id", name=op.f("uq_scenario_set_run_id")),
    )
    op.create_index(
        op.f("ix_scenario_set_behaviour_id"), "scenario_set", ["behaviour_id"], unique=False
    )
    # Like every child of a run: written while the run is open, read-only after.
    op.execute(
        """
        CREATE TRIGGER scenario_set_read_only_when_run_finished
        BEFORE INSERT OR UPDATE OR DELETE ON scenario_set
        FOR EACH ROW EXECUTE FUNCTION agora_run_child_guard();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER scenario_set_read_only_when_run_finished ON scenario_set")
    op.drop_index(op.f("ix_scenario_set_behaviour_id"), table_name="scenario_set")
    op.drop_table("scenario_set")
    # Generation runs cannot survive the old constraint; they are finished, so lift the guards.
    op.execute("ALTER TABLE run DISABLE TRIGGER run_read_only_when_finished")
    op.execute("ALTER TABLE run_sample DISABLE TRIGGER run_sample_read_only_when_run_finished")
    op.execute(
        "DELETE FROM run_sample WHERE run_id IN (SELECT id FROM run WHERE kind = 'scenarios')"
    )
    op.execute("DELETE FROM run WHERE kind = 'scenarios'")
    op.execute("ALTER TABLE run_sample ENABLE TRIGGER run_sample_read_only_when_run_finished")
    op.execute("ALTER TABLE run ENABLE TRIGGER run_read_only_when_finished")
    op.drop_constraint("known_kind", "run", type_="check")
    op.create_check_constraint("known_kind", "run", f"kind IN ({KINDS})")
