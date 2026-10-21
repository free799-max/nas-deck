"""add storage_directories table

Revision ID: f1a2b3c4d5e6
Revises: e2f3a4b5c6d7
Create Date: 2026-10-21 12:00:00.000000

新增数据目录表：记录供大数据量应用使用的可挂载目录，
包含宿主机路径（compose bind source）与容器内路径（后端容器视角）的对应关系。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 storage_directories 表。"""
    op.create_table(
        "storage_directories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), unique=True, nullable=False),
        sa.Column("host_path", sa.String(length=500), nullable=False),
        sa.Column("mount_path", sa.String(length=500), nullable=False),
        sa.Column("remark", sa.String(length=500), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """删除 storage_directories 表。"""
    op.drop_table("storage_directories")
