"""fix app_instances backup_config default to object

backup_config 在模型中是 MutableDict（JSON 对象），但数据库列默认值是
'[]'::json（数组），裸 INSERT 产生的数组行会让 SQLAlchemy 加载时报
ValueError，导致实例列表接口 500。

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-10-20 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """列默认值改为 '{}'，存量数组行回填为 '{}'。"""
    op.alter_column(
        "app_instances",
        "backup_config",
        server_default=sa.text("'{}'::json"),
    )
    op.execute(
        "UPDATE app_instances SET backup_config='{}'::json "
        "WHERE jsonb_typeof(backup_config::jsonb) = 'array'"
    )


def downgrade() -> None:
    """恢复列默认值为 '[]'（不推荐，仅为可回滚）。"""
    op.alter_column(
        "app_instances",
        "backup_config",
        server_default=sa.text("'[]'::json"),
    )
