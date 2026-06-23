"""add directory format to moviepilot host_path

Revision ID: 4a38b75f8434
Revises: d552fb162f5c
Create Date: 2026-06-23 11:06:42.296659

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

import app.models  # noqa: F401
from app.models.app_store import App


# revision identifiers, used by Alembic.
revision: str = '4a38b75f8434'
down_revision: Union[str, None] = 'd552fb162f5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _update_host_path_format(schema: dict, add: bool) -> bool:
    """给 volumes.items.properties.host_path 增删 format: directory。"""
    volumes = schema.get("properties", {}).get("volumes", {})
    items = volumes.get("items", {})
    props = items.get("properties", {})
    host_path = props.get("host_path")
    if host_path is None:
        return False

    if add:
        if host_path.get("format") == "directory":
            return False
        host_path["format"] = "directory"
    else:
        if host_path.get("format") != "directory":
            return False
        del host_path["format"]

    return True


def upgrade() -> None:
    """为 MoviePilot 的 volumes.host_path 增加 format: directory。"""
    bind = op.get_bind()
    session = Session(bind=bind)

    app = session.execute(
        select(App).where(App.name == "moviepilot")
    ).scalar_one_or_none()

    if app is None:
        return

    schema = app.config_schema or {}
    if _update_host_path_format(schema, add=True):
        app.config_schema = schema
        flag_modified(app, "config_schema")
        session.commit()


def downgrade() -> None:
    """移除 MoviePilot 的 volumes.host_path 的 format: directory。"""
    bind = op.get_bind()
    session = Session(bind=bind)

    app = session.execute(
        select(App).where(App.name == "moviepilot")
    ).scalar_one_or_none()

    if app is None:
        return

    schema = app.config_schema or {}
    if _update_host_path_format(schema, add=False):
        app.config_schema = schema
        flag_modified(app, "config_schema")
        session.commit()
