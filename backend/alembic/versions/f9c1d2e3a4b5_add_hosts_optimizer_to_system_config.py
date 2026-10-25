"""add hosts optimizer config to system_config

Revision ID: f9c1d2e3a4b5
Revises: d6e7f8a9b0c1
Create Date: 2026-10-24 15:00:00.000000

系统设置新增 Hosts 优选配置：运行模式、间隔、域名、AdGuard 连接信息
以及最近一次运行结果。配置由服务端维护，结果通过独立接口读写。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f9c1d2e3a4b5"
down_revision: Union[str, None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 system_config 增加 Hosts 优选相关字段。"""
    op.add_column(
        "system_config",
        sa.Column(
            "hosts_optimizer_enabled",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "system_config",
        sa.Column(
            "hosts_optimizer_mode",
            sa.String(length=20),
            server_default="manual",
            nullable=False,
        ),
    )
    op.add_column(
        "system_config",
        sa.Column(
            "hosts_optimizer_interval_minutes",
            sa.Integer(),
            server_default="360",
            nullable=False,
        ),
    )
    op.add_column(
        "system_config",
        sa.Column(
            "hosts_optimizer_top_n",
            sa.Integer(),
            server_default="2",
            nullable=False,
        ),
    )
    op.add_column(
        "system_config",
        sa.Column(
            "hosts_optimizer_domains",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )
    op.add_column(
        "system_config",
        sa.Column(
            "hosts_optimizer_adguard_url",
            sa.String(length=500),
            nullable=True,
        ),
    )
    op.add_column(
        "system_config",
        sa.Column(
            "hosts_optimizer_adguard_username",
            sa.String(length=255),
            server_default="admin",
            nullable=False,
        ),
    )
    op.add_column(
        "system_config",
        sa.Column(
            "hosts_optimizer_adguard_password",
            sa.String(length=255),
            server_default="",
            nullable=False,
        ),
    )
    op.add_column(
        "system_config",
        sa.Column(
            "hosts_optimizer_status",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """移除 Hosts 优选相关字段。"""
    op.drop_column("system_config", "hosts_optimizer_status")
    op.drop_column("system_config", "hosts_optimizer_adguard_password")
    op.drop_column("system_config", "hosts_optimizer_adguard_username")
    op.drop_column("system_config", "hosts_optimizer_adguard_url")
    op.drop_column("system_config", "hosts_optimizer_domains")
    op.drop_column("system_config", "hosts_optimizer_top_n")
    op.drop_column("system_config", "hosts_optimizer_interval_minutes")
    op.drop_column("system_config", "hosts_optimizer_mode")
    op.drop_column("system_config", "hosts_optimizer_enabled")
