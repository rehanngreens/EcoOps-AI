"""add workload and features to analyses

Revision ID: 002
Revises: 001
Create Date: 2026-08-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("analyses", sa.Column("workload", sa.JSON(), nullable=True))
    op.add_column("analyses", sa.Column("features", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("analyses", "features")
    op.drop_column("analyses", "workload")
