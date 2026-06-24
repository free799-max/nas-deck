"""fix moviepilot shared passwords

Revision ID: d552fb162f5c
Revises: 556e0d52766d
Create Date: 2026-06-24 11:20:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d552fb162f5c"
down_revision: Union[str, None] = "556e0d52766d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_APP_NAME = "moviepilot"

# 旧模板中硬编码数组索引的写法
_OLD_POSTGRESQL = "{{ postgresql_env[0].value }}"
_OLD_REDIS = "{{ redis_env[0].value }}"

# 新模板中按 key 查找的写法
_NEW_POSTGRESQL = "{{ (postgresql_env | selectattr('key', 'equalto', 'POSTGRES_PASSWORD') | map(attribute='value') | first | default('')) }}"
_NEW_REDIS = "{{ (redis_env | selectattr('key', 'equalto', 'REDIS_PASSWORD') | map(attribute='value') | first | default('')) }}"


def _replace_in_template(template: str | None, old: str, new: str) -> str | None:
    if template is None:
        return None
    return template.replace(old, new)


def _fetchone(bind, stmt):
    """兼容 Alembic Connection 与裸 Engine 的查询。"""
    if isinstance(bind, sa.Engine):
        with bind.connect() as conn:
            row = conn.execute(stmt).fetchone()
            conn.commit()
            return row
    return bind.execute(stmt).fetchone()


def _execute(bind, stmt):
    """兼容 Alembic Connection 与裸 Engine 的 DML。"""
    if isinstance(bind, sa.Engine):
        with bind.connect() as conn:
            conn.execute(stmt)
            conn.commit()
    else:
        bind.execute(stmt)


def upgrade() -> None:
    """将 MoviePilot yaml_template 中的硬编码索引改为按 key 查找。"""
    bind = op.get_bind()
    apps = sa.table("apps", sa.column("name", sa.String), sa.column("yaml_template", sa.Text))

    row = _fetchone(
        bind,
        sa.select(apps.c.yaml_template).where(apps.c.name == _APP_NAME),
    )

    template = row[0] if row else None
    if not template:
        return

    template = _replace_in_template(template, _OLD_POSTGRESQL, _NEW_POSTGRESQL)
    template = _replace_in_template(template, _OLD_REDIS, _NEW_REDIS)

    _execute(
        bind,
        sa.update(apps).where(apps.c.name == _APP_NAME).values(yaml_template=template),
    )


def downgrade() -> None:
    """恢复 MoviePilot yaml_template 中的硬编码索引写法。"""
    bind = op.get_bind()
    apps = sa.table("apps", sa.column("name", sa.String), sa.column("yaml_template", sa.Text))

    row = _fetchone(
        bind,
        sa.select(apps.c.yaml_template).where(apps.c.name == _APP_NAME),
    )

    template = row[0] if row else None
    if not template:
        return

    template = _replace_in_template(template, _NEW_POSTGRESQL, _OLD_POSTGRESQL)
    template = _replace_in_template(template, _NEW_REDIS, _OLD_REDIS)

    _execute(
        bind,
        sa.update(apps).where(apps.c.name == _APP_NAME).values(yaml_template=template),
    )
