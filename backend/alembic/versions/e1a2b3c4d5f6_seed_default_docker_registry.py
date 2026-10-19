"""seed default docker hub registry

原先由 app.database.init_db 完成的默认 Docker Hub 镜像仓库配置初始化，
迁移到 alembic 统一管理（init_db 已删除）。

Revision ID: e1a2b3c4d5f6
Revises: ccfe1536e1fa
Create Date: 2026-10-17 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e1a2b3c4d5f6"
down_revision: Union[str, None] = "ccfe1536e1fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """表为空时插入默认 Docker Hub 镜像仓库配置。"""
    bind = op.get_bind()
    configs = sa.table(
        "docker_mirror_configs",
        sa.column("name", sa.String),
        sa.column("search_api_url", sa.String),
        sa.column("mirror_url", sa.String),
        sa.column("enable_mirror", sa.Boolean),
        sa.column("username", sa.String),
        sa.column("password", sa.String),
        sa.column("is_default", sa.Boolean),
    )
    row = bind.execute(sa.select(sa.func.count()).select_from(configs)).scalar()
    if row:
        return
    bind.execute(
        configs.insert().values(
            name="Docker Hub",
            search_api_url="https://registry.hub.docker.com",
            mirror_url=None,
            enable_mirror=False,
            username=None,
            password=None,
            is_default=True,
        )
    )


def downgrade() -> None:
    """删除默认 Docker Hub 配置。"""
    bind = op.get_bind()
    configs = sa.table(
        "docker_mirror_configs",
        sa.column("name", sa.String),
        sa.column("is_default", sa.Boolean),
    )
    bind.execute(
        configs.delete().where(
            configs.c.name == "Docker Hub",
            configs.c.is_default == True,  # noqa: E712
        )
    )
