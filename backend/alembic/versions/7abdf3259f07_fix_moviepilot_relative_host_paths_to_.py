"""fix moviepilot relative host paths to be relative to docker mount dir

Revision ID: 7abdf3259f07
Revises: d552fb162f5c
Create Date: 2026-06-24 11:14:14.905336

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7abdf3259f07"
down_revision: Union[str, None] = "d552fb162f5c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# MoviePilot 应用名
_APP_NAME = "moviepilot"

# 之前错误地加上的前缀
_WRONG_PREFIX = "docker/"


def _strip_wrong_prefix(schema: dict) -> dict:
    """移除 schema 中 volumes 类数组字段 default host_path 的错误 docker/ 前缀。"""
    if not isinstance(schema, dict):
        return schema

    properties = schema.get("properties") or {}
    for prop in properties.values():
        if not isinstance(prop, dict):
            continue
        if prop.get("type") != "array":
            continue

        items = prop.get("items") or {}
        if not isinstance(items, dict):
            continue
        item_props = items.get("properties") or {}
        if "host_path" not in item_props:
            continue

        default = prop.get("default")
        if not isinstance(default, list):
            continue

        new_default = []
        for row in default:
            if isinstance(row, dict) and isinstance(row.get("host_path"), str):
                host_path = row["host_path"]
                if not host_path.startswith("/") and host_path.startswith(_WRONG_PREFIX):
                    row = {
                        **row,
                        "host_path": host_path[len(_WRONG_PREFIX) :],
                    }
            new_default.append(row)
        prop["default"] = new_default

    return schema


def _add_wrong_prefix(schema: dict) -> dict:
    """为相对 host_path 恢复错误的 docker/ 前缀（降级用）。"""
    if not isinstance(schema, dict):
        return schema

    properties = schema.get("properties") or {}
    for prop in properties.values():
        if not isinstance(prop, dict):
            continue
        if prop.get("type") != "array":
            continue

        items = prop.get("items") or {}
        if not isinstance(items, dict):
            continue
        item_props = items.get("properties") or {}
        if "host_path" not in item_props:
            continue

        default = prop.get("default")
        if not isinstance(default, list):
            continue

        new_default = []
        for row in default:
            if isinstance(row, dict) and isinstance(row.get("host_path"), str):
                host_path = row["host_path"]
                if not host_path.startswith("/") and not host_path.startswith(_WRONG_PREFIX):
                    row = {**row, "host_path": _WRONG_PREFIX + host_path}
            new_default.append(row)
        prop["default"] = new_default

    return schema


def _load_schema(value):
    """兼容不同数据库的 JSON 返回类型。"""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        import json

        return json.loads(value)
    return dict(value)


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
    """将 MoviePilot volumes 默认 host_path 恢复为相对于 Docker 挂载目录。"""
    bind = op.get_bind()
    apps = sa.table("apps", sa.column("name", sa.String), sa.column("config_schema", sa.JSON))

    row = _fetchone(
        bind,
        sa.select(apps.c.config_schema).where(apps.c.name == _APP_NAME),
    )

    schema = _load_schema(row[0] if row else None)
    if not schema:
        return

    schema = _strip_wrong_prefix(schema)
    _execute(
        bind,
        sa.update(apps).where(apps.c.name == _APP_NAME).values(config_schema=schema),
    )


def downgrade() -> None:
    """降级时重新加上 docker/ 前缀。"""
    bind = op.get_bind()
    apps = sa.table("apps", sa.column("name", sa.String), sa.column("config_schema", sa.JSON))

    row = _fetchone(
        bind,
        sa.select(apps.c.config_schema).where(apps.c.name == _APP_NAME),
    )

    schema = _load_schema(row[0] if row else None)
    if not schema:
        return

    schema = _add_wrong_prefix(schema)
    _execute(
        bind,
        sa.update(apps).where(apps.c.name == _APP_NAME).values(config_schema=schema),
    )
