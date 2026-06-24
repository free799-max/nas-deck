"""isolate moviepilot instances by project_name

Revision ID: 3f81ea50a793
Revises: df5d24452f03
Create Date: 2026-06-24 16:53:07.980918

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "3f81ea50a793"
down_revision: Union[str, None] = "df5d24452f03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_APP_NAME = "moviepilot"


def _load_json(value):
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


def _strip_moviepilot_prefix_from_defaults(schema: dict) -> dict:
    """把 volumes 类数组字段 default 中 host_path 的第一层 moviepilot/ 前缀去掉。

    新模板会在渲染时自动拼上 project_name/，实现多实例目录隔离。
    """
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
                if host_path.startswith("moviepilot/"):
                    host_path = host_path[len("moviepilot/") :]
                new_default.append({**row, "host_path": host_path})
            else:
                new_default.append(row)
        prop["default"] = new_default

    return schema


def _add_moviepilot_prefix_to_defaults(schema: dict) -> dict:
    """降级：把 service 级相对路径重新加上 moviepilot/ 前缀。"""
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
                # 只给 moviepilot 服务相关的路径加前缀
                if host_path.startswith("moviepilot/") or host_path.startswith("redis/") or host_path.startswith("postgresql/"):
                    host_path = "moviepilot/" + host_path
                new_default.append({**row, "host_path": host_path})
            else:
                new_default.append(row)
        prop["default"] = new_default

    return schema


def _update_template(template: str | None) -> str | None:
    """更新 MoviePilot YAML 模板，实现容器名和挂载目录的实例隔离。"""
    if template is None:
        return None

    # 1. moviepilot 主服务容器名/hostname 改为 project_name
    template = template.replace(
        "container_name: moviepilot-v2",
        "container_name: {{ project_name }}",
    )
    template = template.replace(
        "hostname: moviepilot-v2",
        "hostname: {{ project_name }}",
    )

    # 2. 给 redis 和 postgresql 添加 container_name（幂等：已存在则跳过）
    if "container_name: {{ project_name }}-redis" not in template:
        template = template.replace(
            "  redis:\n    image: redis",
            "  redis:\n    image: redis\n    container_name: {{ project_name }}-redis",
        )
    if "container_name: {{ project_name }}-postgresql" not in template:
        template = template.replace(
            "  postgresql:\n    image: postgres",
            "  postgresql:\n    image: postgres\n    container_name: {{ project_name }}-postgresql",
        )

    # 3. 相对路径的 host_path 渲染时拼上 project_name/ 前缀；绝对路径保持原样
    # 3.1 处理旧版模板（没有 project_name 前缀）
    template = template.replace(
        "{{ to_host_path(vol.host_path) }}",
        "{{ to_host_path(vol.host_path if vol.host_path.startswith('/') else project_name ~ '/' ~ vol.host_path) }}",
    )
    # 3.2 处理已有 project_name 前缀但无绝对路径判断的模板
    template = template.replace(
        '{{ to_host_path(project_name ~ "/" ~ vol.host_path) }}',
        "{{ to_host_path(vol.host_path if vol.host_path.startswith('/') else project_name ~ '/' ~ vol.host_path) }}",
    )

    return template


def _revert_template(template: str | None) -> str | None:
    """降级：恢复硬编码容器名，去掉 project_name 前缀。"""
    if template is None:
        return None

    # 1. 先恢复 volumes 路径渲染（这里不含 container_name 替换）
    template = template.replace(
        "{{ to_host_path(vol.host_path if vol.host_path.startswith('/') else project_name ~ '/' ~ vol.host_path) }}",
        "{{ to_host_path(vol.host_path) }}",
    )

    # 2. 再去掉 redis/postgresql 的 container_name（必须在替换 {{ project_name }} 之前）
    template = template.replace(
        "\n    container_name: {{ project_name }}-redis",
        "",
    )
    template = template.replace(
        "\n    container_name: {{ project_name }}-postgresql",
        "",
    )

    # 3. 最后恢复 moviepilot 主服务的硬编码容器名/hostname
    template = template.replace(
        "container_name: {{ project_name }}",
        "container_name: moviepilot-v2",
    )
    template = template.replace(
        "hostname: {{ project_name }}",
        "hostname: moviepilot-v2",
    )

    return template


def upgrade() -> None:
    """隔离 MoviePilot 多实例的容器名与挂载目录。"""
    bind = op.get_bind()
    apps = sa.table(
        "apps",
        sa.column("name", sa.String),
        sa.column("config_schema", sa.JSON),
        sa.column("yaml_template", sa.Text),
    )

    row = _fetchone(
        bind,
        sa.select(apps.c.config_schema, apps.c.yaml_template).where(
            apps.c.name == _APP_NAME
        ),
    )
    if not row:
        return

    schema = _load_json(row[0])
    template = row[1]

    schema = _strip_moviepilot_prefix_from_defaults(schema)
    template = _update_template(template)

    _execute(
        bind,
        sa.update(apps)
        .where(apps.c.name == _APP_NAME)
        .values(
            config_schema=schema,
            yaml_template=template,
        ),
    )


def downgrade() -> None:
    """恢复 MoviePilot 硬编码容器名和旧版挂载路径。"""
    bind = op.get_bind()
    apps = sa.table(
        "apps",
        sa.column("name", sa.String),
        sa.column("config_schema", sa.JSON),
        sa.column("yaml_template", sa.Text),
    )

    row = _fetchone(
        bind,
        sa.select(apps.c.config_schema, apps.c.yaml_template).where(
            apps.c.name == _APP_NAME
        ),
    )
    if not row:
        return

    schema = _load_json(row[0])
    template = row[1]

    schema = _add_moviepilot_prefix_to_defaults(schema)
    template = _revert_template(template)

    _execute(
        bind,
        sa.update(apps)
        .where(apps.c.name == _APP_NAME)
        .values(
            config_schema=schema,
            yaml_template=template,
        ),
    )
