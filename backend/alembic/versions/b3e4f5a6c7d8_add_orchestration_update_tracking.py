"""add orchestration changelog, group version snapshot and update events

为"模板更新记录 + 实例组版本快照 + 一键升级"提供数据支撑：

1. ``app_orchestrations`` 新增 ``changelog``：管理端当前版本的更新说明。
2. ``app_orchestration_instances`` 新增 ``orchestration_version``：
   部署/升级时的方案模板版本快照（区别于 ``app_instances.orchestration_version``，
   后者记录的是应用自身版本）。
3. 新增 ``orchestration_update_events``：模板同步与实例组升级的变更记录。

改动均为可空列或新表，存量数据无需回填。

Revision ID: b3e4f5a6c7d8
Revises: a2b3c4d5e6f7
Create Date: 2026-10-23 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b3e4f5a6c7d8"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新增模板 changelog、实例组版本快照与更新事件表。"""
    # SQLite 不支持 ALTER COLUMN，统一走 batch 模式（PG 下等价于普通 ALTER）
    with op.batch_alter_table("app_orchestrations") as batch_op:
        batch_op.add_column(sa.Column("changelog", sa.Text(), nullable=True))

    with op.batch_alter_table("app_orchestration_instances") as batch_op:
        batch_op.add_column(
            sa.Column("orchestration_version", sa.String(length=20), nullable=True)
        )

    op.create_table(
        "orchestration_update_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("orchestration_name", sa.String(length=50), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("from_version", sa.String(length=20), nullable=True),
        sa.Column("to_version", sa.String(length=20), nullable=True),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_orchestration_update_events_orchestration_name",
        "orchestration_update_events",
        ["orchestration_name"],
    )
    op.create_index(
        "ix_orchestration_update_events_group_id",
        "orchestration_update_events",
        ["group_id"],
    )
    op.create_index(
        "ix_orchestration_update_events_created_at",
        "orchestration_update_events",
        ["created_at"],
    )


def downgrade() -> None:
    """回滚更新事件表与两个新增列。"""
    op.drop_index(
        "ix_orchestration_update_events_created_at",
        table_name="orchestration_update_events",
    )
    op.drop_index(
        "ix_orchestration_update_events_group_id",
        table_name="orchestration_update_events",
    )
    op.drop_index(
        "ix_orchestration_update_events_orchestration_name",
        table_name="orchestration_update_events",
    )
    op.drop_table("orchestration_update_events")

    with op.batch_alter_table("app_orchestration_instances") as batch_op:
        batch_op.drop_column("orchestration_version")

    with op.batch_alter_table("app_orchestrations") as batch_op:
        batch_op.drop_column("changelog")
