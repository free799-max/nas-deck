"""unify compose project paths and drop name

Revision ID: 662f2ffdcd8c
Revises: e36c1d1a69d4
Create Date: 2026-06-14 08:46:55.358160

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '662f2ffdcd8c'
down_revision: Union[str, None] = 'e36c1d1a69d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    insp = inspect(bind)
    project_cols = {c["name"] for c in insp.get_columns("docker_compose_projects")}

    with op.batch_alter_table("docker_compose_projects") as batch_op:
        if "config_files" not in project_cols:
            batch_op.add_column(sa.Column("config_files", sa.Text(), nullable=True))
        if "working_dir" not in project_cols:
            batch_op.add_column(
                sa.Column("working_dir", sa.String(length=500), nullable=True)
            )
        if "name" in project_cols:
            batch_op.drop_column("name")


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    insp = inspect(bind)
    project_cols = {c["name"] for c in insp.get_columns("docker_compose_projects")}

    with op.batch_alter_table("docker_compose_projects") as batch_op:
        if "config_files" in project_cols:
            batch_op.drop_column("config_files")
        if "working_dir" in project_cols:
            batch_op.drop_column("working_dir")
        if "name" not in project_cols:
            batch_op.add_column(
                sa.Column("name", sa.String(length=100), nullable=False)
            )
