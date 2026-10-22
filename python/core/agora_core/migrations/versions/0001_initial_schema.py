"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-21 11:34:07.398611
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("owner", sa.String(length=200), nullable=False),
        sa.Column("domains", postgresql.ARRAY(sa.String(length=32)), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "domains <@ ARRAY['claims', 'coverage', 'disputes', 'health_support']::varchar[]",
            name=op.f("ck_agent_known_domains"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent")),
        sa.UniqueConstraint("key", name=op.f("uq_agent_key")),
    )
    op.create_table(
        "behaviour",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("seed_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("seed_hash", sa.String(length=64), nullable=False),
        sa.Column("git_commit", sa.String(length=64), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_behaviour")),
        sa.UniqueConstraint("key", "seed_hash", name=op.f("uq_behaviour_key_seed_hash")),
    )
    op.create_table(
        "taxonomy_version",
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("git_commit", sa.String(length=64), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_taxonomy_version")),
        sa.UniqueConstraint("version", name=op.f("uq_taxonomy_version_version")),
    )
    op.create_table(
        "user",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("oidc_issuer", sa.String(length=500), nullable=False),
        sa.Column("oidc_subject", sa.String(length=255), nullable=False),
        sa.Column(
            "roles", postgresql.ARRAY(sa.String(length=32)), server_default="{}", nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("sensitive_opt_in", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "roles <@ ARRAY['author', 'reviewer', 'compliance', 'admin']::varchar[]",
            name=op.f("ck_user_known_roles"),
        ),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_user_email_lowercase")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user")),
        sa.UniqueConstraint("email", name=op.f("uq_user_email")),
        sa.UniqueConstraint(
            "oidc_issuer", "oidc_subject", name=op.f("uq_user_oidc_issuer_oidc_subject")
        ),
    )
    op.create_table(
        "audit_event",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(length=100), nullable=True),
        sa.Column(
            "detail", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["user.id"], name=op.f("fk_audit_event_actor_id_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_event")),
    )
    op.create_index(op.f("ix_audit_event_at"), "audit_event", ["at"], unique=False)
    op.create_index(
        op.f("ix_audit_event_target_type"),
        "audit_event",
        ["target_type", "target_id"],
        unique=False,
    )
    op.create_table(
        "data_import",
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("filename", sa.String(length=300), nullable=False),
        sa.Column("object_key", sa.String(length=1000), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "findings", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("uploaded_by", sa.UUID(), nullable=False),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('clean', 'blocked', 'approved', 'rejected')",
            name=op.f("ck_data_import_known_status"),
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["user.id"], name=op.f("fk_data_import_decided_by_user")
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["user.id"], name=op.f("fk_data_import_uploaded_by_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_import")),
    )
    op.create_table(
        "gold_set",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("taxonomy_version_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["taxonomy_version_id"],
            ["taxonomy_version.id"],
            name=op.f("fk_gold_set_taxonomy_version_id_taxonomy_version"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gold_set")),
        sa.UniqueConstraint("name", name=op.f("uq_gold_set_name")),
    )
    op.create_table(
        "label",
        sa.Column("taxonomy_version_id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("family", sa.String(length=50), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("examples", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("counter_examples", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source", sa.String(length=300), nullable=False),
        sa.Column("trust_status", sa.String(length=20), server_default="unrated", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "trust_status IN ('unrated', 'provisional', 'trusted', 'retired')",
            name=op.f("ck_label_known_trust_status"),
        ),
        sa.ForeignKeyConstraint(
            ["taxonomy_version_id"],
            ["taxonomy_version.id"],
            name=op.f("fk_label_taxonomy_version_id_taxonomy_version"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_label")),
        sa.UniqueConstraint(
            "taxonomy_version_id", "key", name=op.f("uq_label_taxonomy_version_id_key")
        ),
    )
    op.create_table(
        "persona",
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("profile", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tone", sa.String(length=200), server_default="", nullable=False),
        sa.Column(
            "risk_flags",
            postgresql.ARRAY(sa.String(length=50)),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"], name=op.f("fk_persona_agent_id_agent")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_persona")),
        sa.UniqueConstraint("agent_id", "key", name=op.f("uq_persona_agent_id_key")),
    )
    op.create_table(
        "prompt_version",
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("git_commit", sa.String(length=64), nullable=False),
        sa.Column("source_path", sa.String(length=500), nullable=False),
        sa.Column("author", sa.String(length=200), nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agent.id"], name=op.f("fk_prompt_version_agent_id_agent")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prompt_version")),
        sa.UniqueConstraint("agent_id", "sha256", name=op.f("uq_prompt_version_agent_id_sha256")),
        sa.UniqueConstraint("agent_id", "version", name=op.f("uq_prompt_version_agent_id_version")),
    )
    op.create_table(
        "system_check",
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=True),
        sa.Column("job_id", sa.BigInteger(), nullable=True),
        sa.Column("object_key", sa.String(length=1000), nullable=True),
        sa.Column(
            "detail", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name=op.f("ck_system_check_known_status"),
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["user.id"], name=op.f("fk_system_check_requested_by_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_system_check")),
    )
    op.create_table(
        "tool_profile",
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("tools", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fixtures", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("git_commit", sa.String(length=64), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agent.id"], name=op.f("fk_tool_profile_agent_id_agent")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_profile")),
        sa.UniqueConstraint("agent_id", "sha256", name=op.f("uq_tool_profile_agent_id_sha256")),
    )
    op.create_table(
        "user_session",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id_token_hint", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name=op.f("fk_user_session_user_id_user"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("token_hash", name=op.f("pk_user_session")),
    )
    op.create_table(
        "agreement",
        sa.Column("gold_set_id", sa.UUID(), nullable=False),
        sa.Column("label_id", sa.UUID(), nullable=False),
        sa.Column("comparison", sa.String(length=20), nullable=False),
        sa.Column("judge_model", sa.String(length=200), nullable=True),
        sa.Column("alpha", sa.Float(), nullable=True),
        sa.Column("n_units", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "comparison IN ('expert_expert', 'judge_expert')",
            name=op.f("ck_agreement_known_comparison"),
        ),
        sa.ForeignKeyConstraint(
            ["gold_set_id"], ["gold_set.id"], name=op.f("fk_agreement_gold_set_id_gold_set")
        ),
        sa.ForeignKeyConstraint(
            ["label_id"], ["label.id"], name=op.f("fk_agreement_label_id_label")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agreement")),
    )
    op.create_table(
        "expected_profile",
        sa.Column("taxonomy_version_id", sa.UUID(), nullable=False),
        sa.Column("scenario_type", sa.String(length=100), nullable=False),
        sa.Column("label_id", sa.UUID(), nullable=False),
        sa.Column("expectation", sa.String(length=10), nullable=False),
        sa.Column("intensity_min", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("intensity_max", sa.SmallInteger(), server_default="3", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "expectation IN ('present', 'absent', 'either')",
            name=op.f("ck_expected_profile_known_expectation"),
        ),
        sa.CheckConstraint(
            "intensity_min BETWEEN 0 AND 3 AND intensity_max BETWEEN 0 AND 3 AND intensity_min <= intensity_max",
            name=op.f("ck_expected_profile_intensity_band"),
        ),
        sa.ForeignKeyConstraint(
            ["label_id"], ["label.id"], name=op.f("fk_expected_profile_label_id_label")
        ),
        sa.ForeignKeyConstraint(
            ["taxonomy_version_id"],
            ["taxonomy_version.id"],
            name=op.f("fk_expected_profile_taxonomy_version_id_taxonomy_version"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expected_profile")),
        sa.UniqueConstraint(
            "taxonomy_version_id",
            "scenario_type",
            "label_id",
            name=op.f("uq_expected_profile_taxonomy_version_id_scenario_type_label_id"),
        ),
    )
    op.create_table(
        "scenario",
        sa.Column("key", sa.String(length=150), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("situation", sa.Text(), nullable=False),
        sa.Column("scenario_type", sa.String(length=100), nullable=True),
        sa.Column(
            "domain_tags",
            postgresql.ARRAY(sa.String(length=50)),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "risk_tags", postgresql.ARRAY(sa.String(length=50)), server_default="{}", nullable=False
        ),
        sa.Column(
            "content_notes",
            postgresql.ARRAY(sa.String(length=50)),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("seed_text", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("persona_id", sa.UUID(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["persona_id"], ["persona.id"], name=op.f("fk_scenario_persona_id_persona")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenario")),
        sa.UniqueConstraint("key", "sha256", name=op.f("uq_scenario_key_sha256")),
    )
    op.create_table(
        "run",
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("title", sa.String(length=300), server_default="", nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("prompt_version_id", sa.UUID(), nullable=True),
        sa.Column("tool_profile_id", sa.UUID(), nullable=True),
        sa.Column("scenario_id", sa.UUID(), nullable=True),
        sa.Column("behaviour_id", sa.UUID(), nullable=True),
        sa.Column("source_run_id", sa.UUID(), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("git_commit", sa.String(length=64), nullable=False),
        sa.Column("prompt_sha", sa.String(length=64), nullable=True),
        sa.Column("seed_hash", sa.String(length=64), nullable=True),
        sa.Column("taxonomy_version", sa.String(length=50), nullable=True),
        sa.Column("model_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("adapter_mode", sa.String(length=20), nullable=True),
        sa.Column("route", sa.String(length=50), nullable=True),
        sa.Column(
            "engine_versions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("token_budget", sa.BigInteger(), nullable=False),
        sa.Column("tokens_used", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "cost_usd", sa.Numeric(precision=12, scale=4), server_default="0", nullable=False
        ),
        sa.Column("log_uri", sa.String(length=1000), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("launched_by", sa.UUID(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('inquiry', 'tally', 'ethos', 'rehearsal')", name=op.f("ck_run_known_kind")
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'stopped_at_budget')",
            name=op.f("ck_run_known_status"),
        ),
        sa.CheckConstraint("token_budget > 0", name=op.f("ck_run_positive_budget")),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"], name=op.f("fk_run_agent_id_agent")),
        sa.ForeignKeyConstraint(
            ["behaviour_id"], ["behaviour.id"], name=op.f("fk_run_behaviour_id_behaviour")
        ),
        sa.ForeignKeyConstraint(["launched_by"], ["user.id"], name=op.f("fk_run_launched_by_user")),
        sa.ForeignKeyConstraint(
            ["prompt_version_id"],
            ["prompt_version.id"],
            name=op.f("fk_run_prompt_version_id_prompt_version"),
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"], ["scenario.id"], name=op.f("fk_run_scenario_id_scenario")
        ),
        sa.ForeignKeyConstraint(
            ["source_run_id"], ["run.id"], name=op.f("fk_run_source_run_id_run")
        ),
        sa.ForeignKeyConstraint(
            ["tool_profile_id"],
            ["tool_profile.id"],
            name=op.f("fk_run_tool_profile_id_tool_profile"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_run")),
    )
    op.create_index(op.f("ix_run_kind"), "run", ["kind", "created_at"], unique=False)
    op.create_table(
        "run_sample",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("sample_index", sa.Integer(), nullable=False),
        sa.Column("epoch", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tokens_used", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("log_uri", sa.String(length=1000), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'stopped_at_budget')",
            name=op.f("ck_run_sample_known_status"),
        ),
        sa.ForeignKeyConstraint(["run_id"], ["run.id"], name=op.f("fk_run_sample_run_id_run")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_run_sample")),
        sa.UniqueConstraint(
            "run_id", "sample_index", "epoch", name=op.f("uq_run_sample_run_id_sample_index_epoch")
        ),
    )
    op.create_table(
        "transcript",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("scenario_id", sa.UUID(), nullable=True),
        sa.Column("sample_index", sa.Integer(), nullable=False),
        sa.Column("epoch", sa.Integer(), server_default="1", nullable=False),
        sa.Column("inspect_sample_id", sa.String(length=200), nullable=True),
        sa.Column("log_uri", sa.String(length=1000), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "meta", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["run.id"], name=op.f("fk_transcript_run_id_run")),
        sa.ForeignKeyConstraint(
            ["scenario_id"], ["scenario.id"], name=op.f("fk_transcript_scenario_id_scenario")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transcript")),
        sa.UniqueConstraint(
            "run_id", "sample_index", "epoch", name=op.f("uq_transcript_run_id_sample_index_epoch")
        ),
    )
    op.create_table(
        "gold_item",
        sa.Column("gold_set_id", sa.UUID(), nullable=False),
        sa.Column("transcript_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["gold_set_id"], ["gold_set.id"], name=op.f("fk_gold_item_gold_set_id_gold_set")
        ),
        sa.ForeignKeyConstraint(
            ["transcript_id"], ["transcript.id"], name=op.f("fk_gold_item_transcript_id_transcript")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gold_item")),
        sa.UniqueConstraint(
            "gold_set_id", "transcript_id", name=op.f("uq_gold_item_gold_set_id_transcript_id")
        ),
    )
    op.create_table(
        "message",
        sa.Column("transcript_id", sa.UUID(), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("thinking_summary", sa.Text(), nullable=True),
        sa.Column("thinking_full", sa.Text(), nullable=True),
        sa.Column("tool_calls", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tool_call_id", sa.String(length=200), nullable=True),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column(
            "meta", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "role IN ('system', 'user', 'assistant', 'tool')", name=op.f("ck_message_known_role")
        ),
        sa.ForeignKeyConstraint(
            ["transcript_id"], ["transcript.id"], name=op.f("fk_message_transcript_id_transcript")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message")),
        sa.UniqueConstraint("transcript_id", "index", name=op.f("uq_message_transcript_id_index")),
    )
    op.create_table(
        "score",
        sa.Column("transcript_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("dimension", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("scale_max", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column(
            "highlights",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("judge_model", sa.String(length=200), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["transcript_id"], ["transcript.id"], name=op.f("fk_score_transcript_id_transcript")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_score")),
        sa.UniqueConstraint(
            "transcript_id",
            "source",
            "dimension",
            name=op.f("uq_score_transcript_id_source_dimension"),
        ),
    )
    op.create_table(
        "annotation",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("label_id", sa.UUID(), nullable=False),
        sa.Column("judge_model", sa.String(length=200), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("intensity", sa.SmallInteger(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("channel", sa.String(length=20), server_default="content", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_start >= 0 AND char_end > char_start", name=op.f("ck_annotation_offsets")
        ),
        sa.CheckConstraint("intensity BETWEEN 0 AND 3", name=op.f("ck_annotation_intensity_range")),
        sa.ForeignKeyConstraint(
            ["label_id"], ["label.id"], name=op.f("fk_annotation_label_id_label")
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["message.id"], name=op.f("fk_annotation_message_id_message")
        ),
        sa.ForeignKeyConstraint(["run_id"], ["run.id"], name=op.f("fk_annotation_run_id_run")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_annotation")),
    )
    op.create_index(
        op.f("ix_annotation_message_id"), "annotation", ["message_id", "label_id"], unique=False
    )
    op.create_table(
        "witness_signal",
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("token_start", sa.Integer(), nullable=False),
        sa.Column("token_end", sa.Integer(), nullable=False),
        sa.Column("values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('probe', 'persona_vector', 'nla')",
            name=op.f("ck_witness_signal_known_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["message.id"], name=op.f("fk_witness_signal_message_id_message")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_witness_signal")),
    )
    op.create_table(
        "dropped_finding",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=True),
        sa.Column("judge_model", sa.String(length=200), nullable=False),
        sa.Column("label_key", sa.String(length=100), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["message.id"], name=op.f("fk_dropped_finding_message_id_message")
        ),
        sa.ForeignKeyConstraint(["run_id"], ["run.id"], name=op.f("fk_dropped_finding_run_id_run")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dropped_finding")),
    )
    op.create_table(
        "gold_label",
        sa.Column("gold_item_id", sa.UUID(), nullable=False),
        sa.Column("labeller_id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("label_id", sa.UUID(), nullable=False),
        sa.Column("intensity", sa.SmallInteger(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("intensity BETWEEN 0 AND 3", name=op.f("ck_gold_label_intensity_range")),
        sa.ForeignKeyConstraint(
            ["gold_item_id"], ["gold_item.id"], name=op.f("fk_gold_label_gold_item_id_gold_item")
        ),
        sa.ForeignKeyConstraint(
            ["label_id"], ["label.id"], name=op.f("fk_gold_label_label_id_label")
        ),
        sa.ForeignKeyConstraint(
            ["labeller_id"], ["user.id"], name=op.f("fk_gold_label_labeller_id_user")
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["message.id"], name=op.f("fk_gold_label_message_id_message")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gold_label")),
        sa.UniqueConstraint(
            "gold_item_id",
            "labeller_id",
            "message_id",
            "label_id",
            name=op.f("uq_gold_label_gold_item_id_labeller_id_message_id_label_id"),
        ),
    )
    op.create_table(
        "review",
        sa.Column("reviewer_id", sa.UUID(), nullable=False),
        sa.Column("annotation_id", sa.UUID(), nullable=True),
        sa.Column("score_id", sa.UUID(), nullable=True),
        sa.Column("verdict", sa.String(length=10), nullable=False),
        sa.Column("corrected_intensity", sa.SmallInteger(), nullable=True),
        sa.Column("corrected_value", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "verdict IN ('agree', 'disagree', 'unsure')", name=op.f("ck_review_known_verdict")
        ),
        sa.CheckConstraint(
            "(annotation_id IS NULL) <> (score_id IS NULL)", name=op.f("ck_review_one_target")
        ),
        sa.CheckConstraint(
            "corrected_intensity IS NULL OR corrected_intensity BETWEEN 0 AND 3",
            name=op.f("ck_review_intensity_range"),
        ),
        sa.ForeignKeyConstraint(
            ["annotation_id"], ["annotation.id"], name=op.f("fk_review_annotation_id_annotation")
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"], ["user.id"], name=op.f("fk_review_reviewer_id_user")
        ),
        sa.ForeignKeyConstraint(["score_id"], ["score.id"], name=op.f("fk_review_score_id_score")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review")),
    )


def downgrade() -> None:
    op.drop_table("review")
    op.drop_table("gold_label")
    op.drop_table("dropped_finding")
    op.drop_table("witness_signal")
    op.drop_index(op.f("ix_annotation_message_id"), table_name="annotation")
    op.drop_table("annotation")
    op.drop_table("score")
    op.drop_table("message")
    op.drop_table("gold_item")
    op.drop_table("transcript")
    op.drop_table("run_sample")
    op.drop_index(op.f("ix_run_kind"), table_name="run")
    op.drop_table("run")
    op.drop_table("scenario")
    op.drop_table("expected_profile")
    op.drop_table("agreement")
    op.drop_table("user_session")
    op.drop_table("tool_profile")
    op.drop_table("system_check")
    op.drop_table("prompt_version")
    op.drop_table("persona")
    op.drop_table("label")
    op.drop_table("gold_set")
    op.drop_table("data_import")
    op.drop_index(op.f("ix_audit_event_target_type"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_at"), table_name="audit_event")
    op.drop_table("audit_event")
    op.drop_table("user")
    op.drop_table("taxonomy_version")
    op.drop_table("behaviour")
    op.drop_table("agent")
