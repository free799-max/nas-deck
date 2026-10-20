"""add service_port_start to system_config

系统设置新增「服务起始端口」：创建服务时从该端口开始按顺序分配，
自动跳过已占用端口。

Revision ID: b7c8d9e0f1a2
Revises: e1a2b3c4d5f6
Create Date: 2026-10-19 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "e1a2b3c4d5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新增 service_port_start 列，存量记录回填默认值 10000。"""
    op.add_column(
        "system_config",
        sa.Column(
            "service_port_start",
            sa.Integer(),
            server_default="10000",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """删除 service_port_start 列。"""
    op.drop_column("system_config", "service_port_start")
