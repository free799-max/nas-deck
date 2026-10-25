"""add proxy_enabled to system_config

Revision ID: c1d2e3f4a5b6
Revises: b8c9d0e1f2a3
Create Date: 2026-10-25 10:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "system_config",
        sa.Column(
            "proxy_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # 已配置代理的存量记录默认保持启用，避免升级后代理失效
    op.execute(
        sa.text(
            "UPDATE system_config SET proxy_enabled = true "
            "WHERE http_proxy IS NOT NULL OR https_proxy IS NOT NULL"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("system_config") as batch_op:
        batch_op.drop_column("proxy_enabled")
