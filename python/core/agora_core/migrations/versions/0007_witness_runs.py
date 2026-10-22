"""witness runs: signals belong to a run, carry character offsets, and are read-only
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

KINDS = "'inquiry', 'tally', 'ethos', 'rehearsal', 'scenarios'"


def upgrade() -> None:
    op.drop_constraint("known_kind", "run", type_="check")
    op.create_check_constraint("known_kind", "run", f"kind IN ({KINDS}, 'witness')")
    # Nothing wrote witness signals before this revision, so the table is empty and
    # the new columns can be required from the start.
    op.add_column("witness_signal", sa.Column("run_id", sa.UUID(), nullable=False))
    op.add_column("witness_signal", sa.Column("char_start", sa.Integer(), nullable=False))
    op.add_column("witness_signal", sa.Column("char_end", sa.Integer(), nullable=False))
    op.add_column(
        "witness_signal",
        sa.Column("offsets", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_foreign_key(
        op.f("fk_witness_signal_run_id_run"), "witness_signal", "run", ["run_id"], ["id"]
    )
    op.create_index("ix_witness_signal_run_message", "witness_signal", ["run_id", "message_id"])
    op.execute(
        """
        CREATE TRIGGER witness_signal_read_only_when_run_finished
        BEFORE INSERT OR UPDATE OR DELETE ON witness_signal
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
    # Finished rows are guarded, so lift the guards while witness runs are removed.
    op.execute("ALTER TABLE run DISABLE TRIGGER run_read_only_when_finished")
    op.execute("ALTER TABLE run_sample DISABLE TRIGGER run_sample_read_only_when_run_finished")
    op.execute("DROP TRIGGER witness_signal_read_only_when_run_finished ON witness_signal")
    op.execute("DELETE FROM witness_signal")
    op.execute("DELETE FROM run_sample WHERE run_id IN (SELECT id FROM run WHERE kind = 'witness')")
    op.execute("DELETE FROM run WHERE kind = 'witness'")
    op.drop_column("run_sample", "detail")
    op.execute("ALTER TABLE run_sample ENABLE TRIGGER run_sample_read_only_when_run_finished")
    op.execute("ALTER TABLE run ENABLE TRIGGER run_read_only_when_finished")
    op.drop_index("ix_witness_signal_run_message", table_name="witness_signal")
    op.drop_constraint(op.f("fk_witness_signal_run_id_run"), "witness_signal", type_="foreignkey")
    for column in ("offsets", "char_end", "char_start", "run_id"):
        op.drop_column("witness_signal", column)
    op.drop_constraint("known_kind", "run", type_="check")
    op.create_check_constraint("known_kind", "run", f"kind IN ({KINDS})")
