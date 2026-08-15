"""Add band_source + override_rule_code to decisions.

Audit finding: the API response had no way to tell a caller whether
decision_band came from the model score alone or was forced/bumped by a
rule (band_resolver.py's critical->decline / high->step_up_auth override).
The frontend could not answer "does it correctly show rule overrides?"
because the backend never recorded it. Persisting it at scoring time (rather
than trying to recompute it later from current threshold rows, which can
have been retuned since) is what makes idempotent replay of an old decision
still report the override truthfully.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "decisions",
        sa.Column("band_source", sa.String(16), nullable=False, server_default="model_score"),
    )
    op.add_column("decisions", sa.Column("override_rule_code", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("decisions", "override_rule_code")
    op.drop_column("decisions", "band_source")
