"""Add policy_version (decision_thresholds + decisions) and split latency
into inference_time_ms / explainability_time_ms alongside the existing total
processing_time_ms on decisions.

Why a new migration instead of editing 0001: 0001 has already been applied
against a database with real seeded/scored data (customer/merchant/device
history from the CSV backfill, live-scored test transactions) -- editing an
already-applied migration is how you end up with a dev DB that no longer
matches what `alembic upgrade head` would produce from scratch elsewhere.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "decision_thresholds",
        sa.Column("policy_version", sa.String(64), nullable=False, server_default="unversioned"),
    )
    op.add_column("decisions", sa.Column("policy_version", sa.String(64), nullable=True))
    op.add_column("decisions", sa.Column("inference_time_ms", sa.Integer(), nullable=True))
    op.add_column("decisions", sa.Column("explainability_time_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("decisions", "explainability_time_ms")
    op.drop_column("decisions", "inference_time_ms")
    op.drop_column("decisions", "policy_version")
    op.drop_column("decision_thresholds", "policy_version")
