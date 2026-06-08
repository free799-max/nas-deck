"""refactor docker mirror config to multi registry

Revision ID: 554ab5394137
Revises: 15101898fbeb
Create Date: 2026-06-08 11:21:53.690431

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '554ab5394137'
down_revision: Union[str, None] = '15101898fbeb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    删除旧的 docker_mirror_configs 表（单条记录，含 registry_mirror 字段），
    重新创建支持多记录的新表，并插入默认的 Docker Hub 官方配置。
    """
    op.drop_table('docker_mirror_configs')
    op.create_table(
        'docker_mirror_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('search_api_url', sa.String(length=500), nullable=False),
        sa.Column('mirror_url', sa.String(length=500), nullable=True),
        sa.Column('enable_mirror', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('password', sa.String(length=100), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    # 插入默认的 Docker Hub 官方配置
    op.execute(
        "INSERT INTO docker_mirror_configs "
        "(name, search_api_url, mirror_url, enable_mirror, username, password, is_default, created_at, updated_at) "
        "VALUES "
        "('Docker Hub 官方', 'https://hub.docker.com/v2/search/repositories', NULL, 0, NULL, NULL, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )


def downgrade() -> None:
    """Downgrade schema.

    恢复为旧的单条记录表结构（数据丢失，仅保留结构回退）。
    """
    op.drop_table('docker_mirror_configs')
    op.create_table(
        'docker_mirror_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('search_api_url', sa.String(length=500), nullable=True),
        sa.Column('registry_mirror', sa.String(length=500), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
