"""add default admin credentials to system_config

统一服务账号：编排部署时自动配置到各服务（MoviePilot、qBittorrent、
Jellyfin），留空密码则每次部署随机生成。

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-10-20 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "system_config",
        sa.Column(
            "default_admin_username",
            sa.String(length=255),
            server_default="admin",
            nullable=False,
        ),
    )
    op.add_column(
        "system_config",
        sa.Column(
            "default_admin_password",
            sa.String(length=255),
            server_default="",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("system_config", "default_admin_password")
    op.drop_column("system_config", "default_admin_username")
