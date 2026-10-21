"""merge storage config into storage_directories

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-10-21 18:00:00.000000

存储配置合并：将 system_config 的 storage_host_root_dir / storage_docker_mount_dir
两个字段合并为 storage_directories 表中 is_app_data=True 的应用数据目录记录。

迁移逻辑：
1. storage_directories 新增 is_app_data 列（默认 False）。
2. 若 system_config.storage_docker_mount_dir 非空，插入一条应用数据目录记录：
   host_path = 旧 storage_docker_mount_dir，
   mount_path = 去掉 storage_host_root_dir 前缀后的容器视角路径（保前导斜杠，
   结果为空时用 host_path 原值做恒等映射），sort_order 取最小值减一使其排最前。
3. 删除 system_config 的两个存储字段列。

回滚说明：storage_host_root_dir 无法从目录记录精确还原，
降级时用 mount_path 推导（host_path 与 mount_path 的公共前缀去除后剩下的
host_path 前缀部分），无法推导时置 '/'，以不丢失应用数据目录路径为先。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalize(path: str | None) -> str:
    """规范化路径：去空白、去尾部斜杠（根目录除外）。"""
    value = (path or "").strip().rstrip("/")
    return value if value else ("/" if (path or "").strip().startswith("/") else "")


def _derive_mount_path(host_root: str, docker_mount: str) -> str:
    """由旧配置推导容器视角挂载路径：docker_mount 去掉 host_root 前缀，保前导斜杠。"""
    host_root = _normalize(host_root)
    docker_mount = _normalize(docker_mount)
    if host_root and docker_mount.startswith(host_root.rstrip("/") + "/"):
        mount = docker_mount[len(host_root.rstrip("/")) :]
    elif docker_mount == host_root:
        mount = ""
    else:
        mount = ""
    if not mount:
        # 无法推导（如两者相同或无前缀关系）时用 host_path 原值做恒等映射
        return docker_mount
    return mount if mount.startswith("/") else f"/{mount}"


def upgrade() -> None:
    """合并存储配置到数据目录表。"""
    # 1. storage_directories 新增 is_app_data 列
    op.add_column(
        "storage_directories",
        sa.Column(
            "is_app_data",
            sa.Boolean(),
            server_default="0",
            nullable=False,
        ),
    )

    # 2. 将旧 system_config 存储配置迁移为应用数据目录记录
    bind = op.get_bind()
    row = bind.execute(
        sa.text(
            "SELECT storage_host_root_dir, storage_docker_mount_dir FROM system_config WHERE id = 1"
        )
    ).fetchone()
    if row and row[1]:
        host_root, docker_mount = row[0], row[1]
        mount_path = _derive_mount_path(host_root, docker_mount)

        # 名称冲突时追加后缀，保证唯一
        name = "应用数据目录"
        existing_names = {
            r[0] for r in bind.execute(sa.text("SELECT name FROM storage_directories"))
        }
        suffix = 2
        candidate = name
        while candidate in existing_names:
            candidate = f"{name} {suffix}"
            suffix += 1
        name = candidate

        # sort_order 取最小值减一，使应用数据目录排在最前；空表时为 0
        min_order = bind.execute(
            sa.text("SELECT MIN(sort_order) FROM storage_directories")
        ).scalar()
        sort_order = (min_order - 1) if min_order is not None else 0

        bind.execute(
            sa.text(
                "INSERT INTO storage_directories "
                "(name, host_path, mount_path, remark, enabled, is_app_data, sort_order, "
                " created_at, updated_at) "
                "VALUES (:name, :host_path, :mount_path, :remark, :enabled, :is_app_data, "
                ":sort_order, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "name": name,
                "host_path": _normalize(docker_mount),
                "mount_path": mount_path,
                "remark": "由系统设置-存储配置迁移而来",
                "enabled": True,
                "is_app_data": True,
                "sort_order": sort_order,
            },
        )

    # 3. 删除 system_config 的两个存储字段列
    with op.batch_alter_table("system_config") as batch_op:
        batch_op.drop_column("storage_host_root_dir")
        batch_op.drop_column("storage_docker_mount_dir")


def downgrade() -> None:
    """还原存储配置到 system_config 字段。"""
    # 1. 加回 system_config 的两个存储字段列
    with op.batch_alter_table("system_config") as batch_op:
        batch_op.add_column(sa.Column("storage_host_root_dir", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("storage_docker_mount_dir", sa.String(length=500), nullable=True))

    # 2. 将 is_app_data 记录还原回 system_config 字段值
    bind = op.get_bind()
    row = bind.execute(
        sa.text(
            "SELECT host_path, mount_path FROM storage_directories WHERE is_app_data = :flag ORDER BY id LIMIT 1"
        ),
        {"flag": True},
    ).fetchone()
    if row:
        host_path, mount_path = row[0], row[1]
        # host_root 无法精确还原：取 host_path 去掉 mount_path 对应后缀后的前缀；
        # 无法推导（如恒等映射）时置 '/'，以不丢失应用数据目录路径为先
        host_root = "/"
        if host_path and mount_path and mount_path != "/" and host_path.endswith(mount_path):
            prefix = host_path[: -len(mount_path)].rstrip("/")
            host_root = prefix if prefix else "/"
        bind.execute(
            sa.text(
                "UPDATE system_config SET storage_host_root_dir = :host_root, "
                "storage_docker_mount_dir = :docker_mount WHERE id = 1"
            ),
            {"host_root": host_root, "docker_mount": host_path},
        )
        # 3. 删除 is_app_data 记录
        bind.execute(
            sa.text("DELETE FROM storage_directories WHERE is_app_data = :flag"),
            {"flag": True},
        )

    # 4. 删除 is_app_data 列
    with op.batch_alter_table("storage_directories") as batch_op:
        batch_op.drop_column("is_app_data")
