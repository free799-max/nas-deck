"""remove default_values from apps and orchestrations

Revision ID: 62a6a8d901e6
Revises: 4b9d682fac3d
Create Date: 2026-06-21 09:39:22.087235

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '62a6a8d901e6'
down_revision: Union[str, None] = '4b9d682fac3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('apps') as batch_op:
        batch_op.drop_column('default_values')

    with op.batch_alter_table('app_orchestrations') as batch_op:
        batch_op.drop_column('default_values')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('apps') as batch_op:
        batch_op.add_column(sa.Column('default_values', sa.JSON(), nullable=False, server_default='{}'))

    with op.batch_alter_table('app_orchestrations') as batch_op:
        batch_op.add_column(sa.Column('default_values', sa.JSON(), nullable=False, server_default='{}'))
