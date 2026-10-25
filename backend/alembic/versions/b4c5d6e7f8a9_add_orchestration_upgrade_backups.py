"""add orchestration upgrade backups

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-10-23 12:00:00.000000

升级编排实例组前保存配置快照（共享配置、应用配置与当前 Compose YAML），
用于升级失败或需要回查旧挂载/端口时恢复。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建升级配置快照表。"""
    op.create_table(
        "orchestration_upgrade_backups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("orchestration_name", sa.String(length=50), nullable=False),
        sa.Column("instance_name", sa.String(length=100), nullable=False),
        sa.Column("from_version", sa.String(length=20), nullable=True),
        sa.Column("to_version", sa.String(length=20), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_orchestration_upgrade_backups_group_id",
        "orchestration_upgrade_backups",
        ["group_id"],
    )
    op.create_index(
        "ix_orchestration_upgrade_backups_created_at",
        "orchestration_upgrade_backups",
        ["created_at"],
    )


def downgrade() -> None:
    """删除升级配置快照表。"""
    op.drop_index(
        "ix_orchestration_upgrade_backups_created_at",
        table_name="orchestration_upgrade_backups",
    )
    op.drop_index(
        "ix_orchestration_upgrade_backups_group_id",
        table_name="orchestration_upgrade_backups",
    )
    op.drop_table("orchestration_upgrade_backups")
