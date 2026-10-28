"""add is_listed to app_orchestrations

Revision ID: c3e8f5a1b9d7
Revises: f6a7b8c9d0e1
Create Date: 2026-10-27 15:00:00.000000

管理端下架的组合仅从历史目录隐藏，不删除本地记录。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c3e8f5a1b9d7"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "app_orchestrations",
        sa.Column(
            "is_listed", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("app_orchestrations") as batch_op:
        batch_op.drop_column("is_listed")
