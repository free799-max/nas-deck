"""add local license state

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-24 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "license_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("installation_id", sa.String(length=36), nullable=False),
        sa.Column("device_name", sa.String(length=255), nullable=True),
        sa.Column("certificate", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("license_id", sa.String(length=128), nullable=True),
        sa.Column("activation_id", sa.String(length=128), nullable=True),
        sa.Column("public_key", sa.Text(), nullable=True),
        sa.Column("key_id", sa.String(length=255), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_license_state_singleton"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("installation_id"),
    )


def downgrade() -> None:
    op.drop_table("license_states")
