"""add original_yaml to analyses

Revision ID: 004
Revises: 003
Create Date: 2026-09-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("analyses", sa.Column("original_yaml", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("analyses", "original_yaml")
