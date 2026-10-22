"""Read-only guards: finished runs, their children, and the audit log

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21 12:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FINISHED = "('succeeded', 'failed', 'cancelled', 'stopped_at_budget')"

# Tables that hang directly off a run, and tables that hang off a transcript.
RUN_CHILDREN = ("run_sample", "transcript", "annotation", "dropped_finding")
TRANSCRIPT_CHILDREN = ("message", "score")


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION agora_refuse_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'agora: % is append-only', TG_TABLE_NAME
                USING ERRCODE = 'restrict_violation';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_event_append_only
        BEFORE UPDATE OR DELETE ON audit_event
        FOR EACH ROW EXECUTE FUNCTION agora_refuse_change();
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION agora_run_finished(target uuid) RETURNS boolean
        LANGUAGE sql STABLE AS $$
            SELECT EXISTS (SELECT 1 FROM run WHERE id = target AND status IN {FINISHED});
        $$;
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION agora_run_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.status IN {FINISHED} THEN
                RAISE EXCEPTION 'agora: run % is finished and read-only', OLD.id
                    USING ERRCODE = 'restrict_violation';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER run_read_only_when_finished
        BEFORE UPDATE OR DELETE ON run
        FOR EACH ROW EXECUTE FUNCTION agora_run_guard();
        """
    )
    op.execute(
        """
        CREATE FUNCTION agora_run_child_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (TG_OP <> 'INSERT' AND agora_run_finished(OLD.run_id))
               OR (TG_OP <> 'DELETE' AND agora_run_finished(NEW.run_id)) THEN
                RAISE EXCEPTION 'agora: % belongs to a finished run', TG_TABLE_NAME
                    USING ERRCODE = 'restrict_violation';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE FUNCTION agora_transcript_child_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            finished boolean;
        BEGIN
            SELECT bool_or(agora_run_finished(t.run_id)) INTO finished
            FROM transcript t
            WHERE t.id IN (
                CASE WHEN TG_OP <> 'INSERT' THEN OLD.transcript_id END,
                CASE WHEN TG_OP <> 'DELETE' THEN NEW.transcript_id END
            );
            IF finished THEN
                RAISE EXCEPTION 'agora: % belongs to a finished run', TG_TABLE_NAME
                    USING ERRCODE = 'restrict_violation';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    for table in RUN_CHILDREN:
        op.execute(
            f"""
            CREATE TRIGGER {table}_read_only_when_run_finished
            BEFORE INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION agora_run_child_guard();
            """
        )
    for table in TRANSCRIPT_CHILDREN:
        op.execute(
            f"""
            CREATE TRIGGER {table}_read_only_when_run_finished
            BEFORE INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION agora_transcript_child_guard();
            """
        )


def downgrade() -> None:
    for table in TRANSCRIPT_CHILDREN + RUN_CHILDREN:
        op.execute(f"DROP TRIGGER {table}_read_only_when_run_finished ON {table}")
    op.execute("DROP TRIGGER run_read_only_when_finished ON run")
    op.execute("DROP TRIGGER audit_event_append_only ON audit_event")
    op.execute("DROP FUNCTION agora_transcript_child_guard()")
    op.execute("DROP FUNCTION agora_run_child_guard()")
    op.execute("DROP FUNCTION agora_run_guard()")
    op.execute("DROP FUNCTION agora_run_finished(uuid)")
    op.execute("DROP FUNCTION agora_refuse_change()")
