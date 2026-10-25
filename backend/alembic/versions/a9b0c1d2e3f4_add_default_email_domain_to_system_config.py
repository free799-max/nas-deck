"""add default email domain to system_config

Revision ID: a9b0c1d2e3f4
Revises: d4e5f6a7b8c9
Create Date: 2026-10-25 10:00:00.000000

统一服务账号新增邮箱后缀配置。仅对必须使用邮箱登录的应用
（Komga、二毛读书）生效，未配置时保持各客户端原有的默认行为。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 system_config 增加邮箱后缀字段。"""
    op.add_column(
        "system_config",
        sa.Column(
            "default_email_domain",
            sa.String(length=255),
            server_default="",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """移除邮箱后缀字段。"""
    op.drop_column("system_config", "default_email_domain")
