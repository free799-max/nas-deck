"""add suggested_plugins to app_orchestrations

Revision ID: 702a6bd8273a
Revises: 96711a0d8040
Create Date: 2026-06-19 20:14:00.035700

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '702a6bd8273a'
down_revision: Union[str, None] = '96711a0d8040'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('app_orchestrations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('suggested_plugins', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('app_orchestrations', schema=None) as batch_op:
        batch_op.drop_column('suggested_plugins')
