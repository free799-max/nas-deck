"""drop unused docker_container and plugin docker_id

Revision ID: 810b8d2acf5e
Revises: 662f2ffdcd8c
Create Date: 2026-06-16 17:02:41.244290

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '810b8d2acf5e'
down_revision: Union[str, None] = '662f2ffdcd8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 删除未使用的 Docker 容器缓存表
    if inspector.has_table("docker_containers"):
        op.drop_table("docker_containers")

    # 删除插件实例中未使用的 docker_id 列
    plugin_columns = [c["name"] for c in inspector.get_columns("plugin_instances")]
    if "docker_id" in plugin_columns:
        op.drop_column("plugin_instances", "docker_id")

    # 删除历史遗留的通知/订阅相关表
    for table_name in ("update_logs", "subscriptions", "notification_channels"):
        if inspector.has_table(table_name):
            op.drop_table(table_name)


def downgrade() -> None:
    """Downgrade schema."""
    # 恢复 notification_channels 表
    op.create_table(
        'notification_channels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    # 恢复 subscriptions 表
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('instance_id', sa.Integer(), nullable=False),
        sa.Column('item_id', sa.String(length=255), nullable=False),
        sa.Column('item_title', sa.String(length=255), nullable=False),
        sa.Column('item_meta', sa.JSON(), nullable=False),
        sa.Column('last_checked', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['instance_id'], ['plugin_instances.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    # 恢复 update_logs 表
    op.create_table(
        'update_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('subscription_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('detected_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('notified', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id']),
        sa.PrimaryKeyConstraint('id')
    )
    # 恢复 plugin_instances.docker_id 列
    op.add_column(
        'plugin_instances',
        sa.Column('docker_id', sa.String(length=100), nullable=True)
    )
    # 恢复 docker_containers 表
    op.create_table(
        'docker_containers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('instance_id', sa.Integer(), nullable=False),
        sa.Column('container_id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('health', sa.String(length=20), nullable=False),
        sa.Column('last_checked', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['instance_id'], ['plugin_instances.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('instance_id')
    )
