"""add generations table

Revision ID: 005
Revises: 004
Create Date: 2026-09-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("workload", sa.JSON(), nullable=False),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("target", sa.String(length=64), nullable=False),
        sa.Column("target_source", sa.String(length=16), nullable=False),
        sa.Column("target_explanation", sa.String(length=2000), nullable=False),
        sa.Column("evaluation", sa.JSON(), nullable=False),
        sa.Column("artifacts", sa.JSON(), nullable=True),
        sa.Column("selected_configuration", sa.JSON(), nullable=True),
        sa.Column("disclaimer", sa.String(length=2000), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_generations_status", "generations", ["status"])
    op.create_index("ix_generations_created_at", "generations", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_generations_created_at", table_name="generations")
    op.drop_index("ix_generations_status", table_name="generations")
    op.drop_table("generations")
