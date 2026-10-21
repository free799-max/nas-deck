"""media-stack 模板 moviepilot integrations 声明迁移逻辑验证。"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.models.orchestration import AppOrchestration


# 通过文件路径加载 alembic 迁移模块（它不是 Python 包的一部分）
_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "alembic"
    / "versions"
    / "e2f3a4b5c6d7_add_moviepilot_integrations_to_media_stack.py"
)
_spec = importlib.util.spec_from_file_location(
    "add_moviepilot_integrations_to_media_stack", _MIGRATION_PATH
)
_migration_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_migration_module)
upgrade = _migration_module.upgrade
downgrade = _migration_module.downgrade

_OLD_COMPOSITION = [
    {"app_name": "moviepilot", "relation": "required"},
    {"app_name": "qbittorrent", "relation": "required"},
    {"app_name": "jellyfin", "relation": "optional", "group": "player"},
    {"app_name": "emby", "relation": "optional", "group": "player"},
]


@pytest.fixture
def db_session():
    """创建内存数据库会话并插入旧版 media-stack 模板数据。"""
    engine = create_engine("sqlite:///:memory:")
    AppOrchestration.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    session.add(
        AppOrchestration(
            name="media-stack",
            display_name="影视自动化",
            category="media",
            app_composition=[dict(item) for item in _OLD_COMPOSITION],
            shared_config_schema={},
        )
    )
    session.commit()

    yield session

    session.close()
    engine.dispose()


def _run_upgrade(session):
    mock_op = MagicMock()
    mock_op.get_bind.return_value = session.bind
    with patch.object(_migration_module, "op", mock_op):
        upgrade()
    session.expire_all()


def _run_downgrade(session):
    mock_op = MagicMock()
    mock_op.get_bind.return_value = session.bind
    with patch.object(_migration_module, "op", mock_op):
        downgrade()
    session.expire_all()


def _get_composition(session):
    orch = session.query(AppOrchestration).filter_by(name="media-stack").one()
    return orch.app_composition


def test_upgrade_adds_integrations_to_moviepilot_only(db_session):
    """升级只为 moviepilot 条目加 integrations，其余条目不破坏。"""
    _run_upgrade(db_session)
    composition = _get_composition(db_session)

    by_name = {item["app_name"]: item for item in composition}
    assert by_name["moviepilot"]["integrations"] == [
        {"type": "downloader", "from": "qbittorrent"},
        {"type": "mediaserver", "from": ["jellyfin", "emby"]},
    ]
    # 其余字段与其他条目保持原样
    assert by_name["moviepilot"]["relation"] == "required"
    assert "integrations" not in by_name["qbittorrent"]
    assert "integrations" not in by_name["jellyfin"]
    assert by_name["jellyfin"]["group"] == "player"


def test_upgrade_is_idempotent(db_session):
    """重复执行升级不会重复添加 integrations。"""
    _run_upgrade(db_session)
    _run_upgrade(db_session)
    composition = _get_composition(db_session)

    moviepilot = next(i for i in composition if i["app_name"] == "moviepilot")
    assert len(moviepilot["integrations"]) == 2


def test_downgrade_removes_integrations(db_session):
    """降级移除 integrations 键并还原其余字段。"""
    _run_upgrade(db_session)
    _run_downgrade(db_session)
    composition = _get_composition(db_session)

    assert composition == _OLD_COMPOSITION
