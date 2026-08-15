"""Initial schema per VALLI SecurePay AI MVP Blueprint Section 4.

Table creation order differs from the blueprint's document order to satisfy
FK dependencies within a single migration (the blueprint has transactions ->
batch_jobs and batch_jobs -> users as forward references): users and
batch_jobs are created before transactions here.

Revision ID: 0001
Revises:
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    # ------------------------------------------------------------------
    # AUTH
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", postgresql.CITEXT(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="analyst"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------
    # CORE REFERENCE ENTITIES
    # ------------------------------------------------------------------
    op.create_table(
        "customers",
        sa.Column("customer_id", sa.String(12), primary_key=True),
        sa.Column("home_country", sa.CHAR(2), nullable=False),
        sa.Column("account_created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("average_transaction_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("customer_risk_score", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("customer_risk_score BETWEEN 0 AND 100", name="ck_customer_risk_score_range"),
    )

    op.create_table(
        "merchants",
        sa.Column("merchant_id", sa.String(12), primary_key=True),
        sa.Column("merchant_category", sa.String(32), nullable=False),
        sa.Column("home_country", sa.CHAR(2), nullable=False),
        sa.Column("merchant_risk_score", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("merchant_risk_score BETWEEN 0 AND 100", name="ck_merchant_risk_score_range"),
    )

    op.create_table(
        "devices",
        sa.Column("device_id", sa.String(14), primary_key=True),
        sa.Column("first_seen_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "customer_devices",
        sa.Column("customer_id", sa.String(12), sa.ForeignKey("customers.customer_id"), primary_key=True),
        sa.Column("device_id", sa.String(14), sa.ForeignKey("devices.device_id"), primary_key=True),
        sa.Column("first_seen_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------
    # MODEL / RULES / THRESHOLDS CONFIG
    # ------------------------------------------------------------------
    op.create_table(
        "model_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("version_tag", sa.String(32), nullable=False, unique=True),
        sa.Column("artifact_uri", sa.Text(), nullable=False),
        sa.Column("pr_auc", sa.Numeric(5, 4)),
        sa.Column("trained_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rule_code", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "decision_thresholds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("band", sa.String(16), nullable=False, unique=True),
        sa.Column("min_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("max_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------
    # BANK CLIENTS -- API-key credentials for integrating banks' backends.
    # Distinct from `users` (humans logging into the analyst console via
    # email/password -> JWT): bank_clients are machine callers authenticating
    # with a long-lived X-API-Key on the scoring/batch API directly.
    # ------------------------------------------------------------------
    op.create_table(
        "bank_clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("bank_name", sa.String(128), nullable=False),
        sa.Column("bank_code", sa.String(16), nullable=False, unique=True),
        sa.Column("api_key_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("api_key_prefix", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True)),
    )

    # ------------------------------------------------------------------
    # BATCH JOBS (created before transactions -- transactions.batch_job_id refs it)
    # ------------------------------------------------------------------
    op.create_table(
        "batch_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("submitted_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("input_uri", sa.Text(), nullable=False),
        sa.Column("output_uri", sa.Text()),
        sa.Column("row_count", sa.Integer()),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------
    # TRANSACTIONS & DECISIONS
    # ------------------------------------------------------------------
    op.create_table(
        "transactions",
        sa.Column("transaction_id", sa.String(14), primary_key=True),
        sa.Column("customer_id", sa.String(12), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("merchant_id", sa.String(12), sa.ForeignKey("merchants.merchant_id"), nullable=False),
        sa.Column("device_id", sa.String(14), sa.ForeignKey("devices.device_id"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("transaction_country", sa.CHAR(2), nullable=False),
        sa.Column("ip_country", sa.CHAR(2), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("is_new_device", sa.Boolean(), nullable=False),
        sa.Column("is_new_beneficiary", sa.Boolean(), nullable=False),
        sa.Column("session_duration_seconds", sa.Integer()),
        sa.Column("transactions_last_10_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_attempts_last_24_hours", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("days_since_last_transaction", sa.Integer()),
        sa.Column("transaction_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("source", sa.String(16), nullable=False, server_default="single"),
        sa.Column("batch_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batch_jobs.id")),
        sa.Column("submitted_by_bank_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bank_clients.id")),
        sa.Column("fraud_label", sa.SmallInteger()),
        sa.Column("fraud_type", sa.String(32)),
        sa.CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
    )
    op.create_index("idx_transactions_customer", "transactions", ["customer_id", sa.text("transaction_time DESC")])
    op.create_index("idx_transactions_merchant", "transactions", ["merchant_id"])
    op.create_index("idx_transactions_device", "transactions", ["device_id"])
    op.create_index("idx_transactions_time", "transactions", [sa.text("transaction_time DESC")])

    op.create_table(
        "decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("transaction_id", sa.String(14), sa.ForeignKey("transactions.transaction_id"), nullable=False),
        sa.Column("model_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("model_versions.id"), nullable=False),
        sa.Column("risk_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("decision_band", sa.String(16), nullable=False),
        sa.Column("summary_reason", sa.Text(), nullable=False),
        sa.Column("contributing_factors", postgresql.JSONB(), nullable=False),
        sa.Column("shap_values", postgresql.JSONB()),
        sa.Column("processing_time_ms", sa.Integer(), nullable=False),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_decisions_transaction", "decisions", ["transaction_id"])
    op.create_index("idx_decisions_band_time", "decisions", ["decision_band", sa.text("decided_at DESC")])

    op.create_table(
        "rule_hits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rules.id"), nullable=False),
        sa.Column("detail", postgresql.JSONB()),
    )
    op.create_index("idx_rule_hits_decision", "rule_hits", ["decision_id"])
    op.create_index("idx_rule_hits_rule", "rule_hits", ["rule_id"])

    # ------------------------------------------------------------------
    # AUDIT
    # ------------------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(32)),
        sa.Column("entity_id", sa.Text()),
        sa.Column("metadata", postgresql.JSONB()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_audit_log_actor", "audit_log", ["actor_user_id", sa.text("created_at DESC")])

    # ------------------------------------------------------------------
    # OVERVIEW DASHBOARD MATERIALIZED VIEW
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_overview_daily AS
        SELECT
            date_trunc('day', d.decided_at) AS day,
            count(*)                          AS transactions_analyzed,
            avg(d.risk_score)                  AS avg_risk_score,
            avg(d.processing_time_ms)            AS avg_processing_time_ms,
            count(*) FILTER (WHERE d.decision_band IN ('decline','manual_review')) * 1.0
                / NULLIF(count(*), 0)              AS decline_hold_rate,
            count(*) FILTER (WHERE d.decision_band = 'monitor')        AS monitor_count,
            count(*) FILTER (WHERE d.decision_band = 'step_up_auth')   AS step_up_count,
            count(*) FILTER (WHERE d.decision_band = 'manual_review')  AS manual_review_count,
            count(*) FILTER (WHERE d.decision_band = 'decline')        AS decline_count
        FROM decisions d
        GROUP BY 1
        """
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_overview_daily")
    op.drop_table("audit_log")
    op.drop_table("rule_hits")
    op.drop_table("decisions")
    op.drop_table("transactions")
    op.drop_table("batch_jobs")
    op.drop_table("bank_clients")
    op.drop_table("decision_thresholds")
    op.drop_table("rules")
    op.drop_table("model_versions")
    op.drop_table("customer_devices")
    op.drop_table("devices")
    op.drop_table("merchants")
    op.drop_table("customers")
    op.drop_table("users")
