"""add license_key to license_states

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-10-25 11:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "license_states",
        sa.Column("license_key", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("license_states") as batch_op:
        batch_op.drop_column("license_key")
