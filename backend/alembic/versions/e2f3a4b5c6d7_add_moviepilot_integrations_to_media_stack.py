"""add moviepilot integrations to media-stack composition

Revision ID: e2f3a4b5c6d7
Revises: d9e0f1a2b3c4
Create Date: 2026-10-20 12:00:00.000000

为 media-stack（影视自动化）模板的 app_composition 中 moviepilot 条目
增加 integrations 声明：部署后自动把 qBittorrent（下载器）与
Jellyfin/Emby（媒体服务器，二选一）装配进 MoviePilot。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ORCHESTRATION_NAME = "media-stack"
_TARGET_APP = "moviepilot"

# moviepilot 条目的集成声明：from 为列表时表示候选来源，取实际部署的那个
_INTEGRATIONS = [
    {"type": "downloader", "from": "qbittorrent"},
    {"type": "mediaserver", "from": ["jellyfin", "emby"]},
]


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


def _orchestrations_table():
    return sa.table(
        "app_orchestrations",
        sa.column("name", sa.String),
        sa.column("app_composition", sa.JSON),
    )


def upgrade() -> None:
    """为 moviepilot 条目添加 integrations 声明，其余字段保持不变。"""
    bind = op.get_bind()
    orchestrations = _orchestrations_table()

    row = _fetchone(
        bind,
        sa.select(orchestrations.c.app_composition).where(
            orchestrations.c.name == _ORCHESTRATION_NAME
        ),
    )
    composition = row[0] if row else None
    if not composition:
        return

    changed = False
    for item in composition:
        if item.get("app_name") == _TARGET_APP and "integrations" not in item:
            item["integrations"] = [dict(spec) for spec in _INTEGRATIONS]
            changed = True
    if not changed:
        return

    _execute(
        bind,
        sa.update(orchestrations)
        .where(orchestrations.c.name == _ORCHESTRATION_NAME)
        .values(app_composition=composition),
    )


def downgrade() -> None:
    """移除 moviepilot 条目的 integrations 声明。"""
    bind = op.get_bind()
    orchestrations = _orchestrations_table()

    row = _fetchone(
        bind,
        sa.select(orchestrations.c.app_composition).where(
            orchestrations.c.name == _ORCHESTRATION_NAME
        ),
    )
    composition = row[0] if row else None
    if not composition:
        return

    changed = False
    for item in composition:
        if item.get("app_name") == _TARGET_APP and "integrations" in item:
            del item["integrations"]
            changed = True
    if not changed:
        return

    _execute(
        bind,
        sa.update(orchestrations)
        .where(orchestrations.c.name == _ORCHESTRATION_NAME)
        .values(app_composition=composition),
    )
