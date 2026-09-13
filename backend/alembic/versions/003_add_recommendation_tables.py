"""add recommendation tables

Revision ID: 003
Revises: 002
Create Date: 2026-09-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendation_sets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "analysis_id",
            sa.String(length=36),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("baseline_configuration", sa.JSON(), nullable=False),
        sa.Column("optimized_configuration", sa.JSON(), nullable=True),
        sa.Column("totals", sa.JSON(), nullable=True),
        sa.Column("rejected_candidates", sa.JSON(), nullable=True),
        sa.Column("explanation", sa.String(length=2000), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "recommendation_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "recommendation_set_id",
            sa.String(length=36),
            sa.ForeignKey("recommendation_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("parameter", sa.String(length=64), nullable=False),
        sa.Column("current_value", sa.String(length=255), nullable=False),
        sa.Column("suggested_value", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=2000), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("recommendation_items")
    op.drop_table("recommendation_sets")
