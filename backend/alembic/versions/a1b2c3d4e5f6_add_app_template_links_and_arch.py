"""add website, source_url, architectures to app_templates

Revision ID: a1b2c3d4e5f6
Revises: 6d0cdf7a7696
Create Date: 2026-06-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '6d0cdf7a7696'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_cols = {c['name'] for c in inspector.get_columns('app_templates')}
    if 'website' not in existing_cols:
        op.add_column('app_templates', sa.Column('website', sa.String(length=255), nullable=True))
    if 'source_url' not in existing_cols:
        op.add_column('app_templates', sa.Column('source_url', sa.String(length=255), nullable=True))
    if 'architectures' not in existing_cols:
        op.add_column('app_templates', sa.Column('architectures', sa.JSON(), server_default=sa.text("'[]'"), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('app_templates', 'architectures')
    op.drop_column('app_templates', 'source_url')
    op.drop_column('app_templates', 'website')
