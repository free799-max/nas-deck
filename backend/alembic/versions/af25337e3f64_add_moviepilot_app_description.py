"""add moviepilot app description

Revision ID: af25337e3f64
Revises: 86740046ee8e
Create Date: 2026-06-26 11:32:21.459436

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af25337e3f64'
down_revision: Union[str, None] = '86740046ee8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 moviepilot 应用补充描述。"""
    op.execute(
        """UPDATE apps
           SET description = 'MoviePilot 是新一代智能化个人媒体库管理工具。'
           WHERE name = 'moviepilot'
             AND (description IS NULL OR description = '');"""
    )


def downgrade() -> None:
    """清空 moviepilot 应用描述。"""
    op.execute(
        """UPDATE apps
           SET description = ''
           WHERE name = 'moviepilot'
             AND description = 'MoviePilot 是新一代智能化个人媒体库管理工具。';"""
    )
