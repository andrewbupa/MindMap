"""companion runs: signals belong to a run, carry character offsets, and are read-only
once the run finishes; run samples gain a detail field

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-21 21:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = "'explore', 'measure', 'lens', 'playground', 'scenarios'"


def upgrade() -> None:
    op.drop_constraint("known_kind", "run", type_="check")
    op.create_check_constraint("known_kind", "run", f"kind IN ({KINDS}, 'companion')")
    # Nothing wrote companion signals before this revision, so the table is empty and
    # the new columns can be required from the start.
    op.add_column("companion_signal", sa.Column("run_id", sa.UUID(), nullable=False))
    op.add_column("companion_signal", sa.Column("char_start", sa.Integer(), nullable=False))
    op.add_column("companion_signal", sa.Column("char_end", sa.Integer(), nullable=False))
    op.add_column(
        "companion_signal",
        sa.Column("offsets", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_foreign_key(
        op.f("fk_companion_signal_run_id_run"), "companion_signal", "run", ["run_id"], ["id"]
    )
    op.create_index("ix_companion_signal_run_message", "companion_signal", ["run_id", "message_id"])
    op.execute(
        """
        CREATE TRIGGER companion_signal_read_only_when_run_finished
        BEFORE INSERT OR UPDATE OR DELETE ON companion_signal
        FOR EACH ROW EXECUTE FUNCTION agora_run_child_guard();
        """
    )
    op.add_column(
        "run_sample",
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade() -> None:
    # Finished rows are guarded, so lift the guards while companion runs are removed.
    op.execute("ALTER TABLE run DISABLE TRIGGER run_read_only_when_finished")
    op.execute("ALTER TABLE run_sample DISABLE TRIGGER run_sample_read_only_when_run_finished")
    op.execute("DROP TRIGGER companion_signal_read_only_when_run_finished ON companion_signal")
    op.execute("DELETE FROM companion_signal")
    op.execute(
        "DELETE FROM run_sample WHERE run_id IN (SELECT id FROM run WHERE kind = 'companion')"
    )
    op.execute("DELETE FROM run WHERE kind = 'companion'")
    op.drop_column("run_sample", "detail")
    op.execute("ALTER TABLE run_sample ENABLE TRIGGER run_sample_read_only_when_run_finished")
    op.execute("ALTER TABLE run ENABLE TRIGGER run_read_only_when_finished")
    op.drop_index("ix_companion_signal_run_message", table_name="companion_signal")
    op.drop_constraint(
        op.f("fk_companion_signal_run_id_run"), "companion_signal", type_="foreignkey"
    )
    for column in ("offsets", "char_end", "char_start", "run_id"):
        op.drop_column("companion_signal", column)
    op.drop_constraint("known_kind", "run", type_="check")
    op.create_check_constraint("known_kind", "run", f"kind IN ({KINDS})")
