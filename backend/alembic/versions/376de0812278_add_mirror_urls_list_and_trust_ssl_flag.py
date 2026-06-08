"""add mirror urls list and trust ssl flag

Revision ID: 376de0812278
Revises: 554ab5394137
Create Date: 2026-06-08 17:18:58.459870

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '376de0812278'
down_revision: Union[str, None] = '554ab5394137'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    添加 mirror_urls 字段（JSON 字符串列表）和 trust_ssl_self_signed 字段。
    """
    op.add_column(
        'docker_mirror_configs',
        sa.Column('mirror_urls', sa.Text(), nullable=True)
    )
    op.add_column(
        'docker_mirror_configs',
        sa.Column('trust_ssl_self_signed', sa.Boolean(), nullable=True, server_default='0')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('docker_mirror_configs', 'trust_ssl_self_signed')
    op.drop_column('docker_mirror_configs', 'mirror_urls')
