"""normalize orchestration categories

Revision ID: e8f6a9b3d0c2
Revises: d7e5f8a2c9b1
Create Date: 2026-10-23 12:00:00.000000

编排模板分类统一为前端分类页使用的 key（media/comics/books/games），
历史上从管理端同步来的 movie / comic / book / game 转换过去。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e8f6a9b3d0c2"
down_revision: Union[str, None] = "d7e5f8a2c9b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LEGACY_TO_CANONICAL = {
    "movie": "media",
    "comic": "comics",
    "book": "books",
    "game": "games",
}


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    for legacy, canonical in _LEGACY_TO_CANONICAL.items():
        bind.execute(
            sa.text(
                "UPDATE app_orchestrations SET category = :canonical "
                "WHERE category = :legacy"
            ),
            {"canonical": canonical, "legacy": legacy},
        )


def downgrade() -> None:
    """Downgrade schema."""
    # 无法区分原本就是新 key 的数据，降级不做反向转换。
    pass
