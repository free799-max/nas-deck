"""add docker_registry_mirrors to system_config

Revision ID: a3b4c5d6e7f8
Revises: e8f6a9b3d0c2
Create Date: 2026-10-23 11:00:00.000000

系统基础配置新增 Docker 镜像加速地址列表（JSON 数组，按优先级排序）。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "e8f6a9b3d0c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 system_config 增加镜像加速地址列表字段。"""
    op.add_column(
        "system_config",
        sa.Column(
            "docker_registry_mirrors",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """移除镜像加速地址列表字段。"""
    op.drop_column("system_config", "docker_registry_mirrors")
