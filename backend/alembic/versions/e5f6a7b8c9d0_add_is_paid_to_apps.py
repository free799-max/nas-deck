"""add is_paid to apps

Revision ID: e5f6a7b8c9d0
Revises: a9b0c1d2e3f4
Create Date: 2026-10-27 12:30:00.000000

应用商店新增 is_paid 字段，同步管理端的付费应用标识。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "a9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "apps",
        sa.Column(
            "is_paid", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("apps") as batch_op:
        batch_op.drop_column("is_paid")
