"""align compose schema

Revision ID: e36c1d1a69d4
Revises: 5af9ea108c0d
Create Date: 2026-06-13 21:43:31.484903

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = 'e36c1d1a69d4'
down_revision: Union[str, None] = '5af9ea108c0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    insp = inspect(bind)
    tables = set(insp.get_table_names())

    # 清理已移除的旧表
    for table_name in ("notification_channels", "subscriptions", "update_logs"):
        if table_name in tables:
            op.drop_table(table_name)

    # 移除 docker_compose_projects 中旧的 current_version_id 字段
    project_cols = {c["name"] for c in insp.get_columns("docker_compose_projects")}
    if "current_version_id" in project_cols:
        with op.batch_alter_table("docker_compose_projects") as batch_op:
            batch_op.drop_column("current_version_id")

    # 为 docker_compose_versions 补充 is_current 字段
    version_cols = {c["name"] for c in insp.get_columns("docker_compose_versions")}
    if "is_current" not in version_cols:
        with op.batch_alter_table("docker_compose_versions") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "is_current",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("'0'"),
                )
            )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    insp = inspect(bind)

    version_cols = {c["name"] for c in insp.get_columns("docker_compose_versions")}
    if "is_current" in version_cols:
        with op.batch_alter_table("docker_compose_versions") as batch_op:
            batch_op.drop_column("is_current")

    project_cols = {c["name"] for c in insp.get_columns("docker_compose_projects")}
    if "current_version_id" not in project_cols:
        with op.batch_alter_table("docker_compose_projects") as batch_op:
            batch_op.add_column(
                sa.Column("current_version_id", sa.Integer(), nullable=True)
            )
