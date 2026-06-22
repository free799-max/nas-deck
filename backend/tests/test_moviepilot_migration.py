"""MoviePilot 共享密码迁移逻辑验证。"""

import importlib.util
from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.models.app_store import App


# 通过文件路径加载 alembic 迁移模块（它不是 Python 包的一部分）
_MIGRATION_PATH = Path(__file__).resolve().parent.parent / "alembic" / "versions" / "d552fb162f5c_fix_moviepilot_shared_passwords.py"
_spec = importlib.util.spec_from_file_location("fix_moviepilot_shared_passwords", _MIGRATION_PATH)
_migration_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_migration_module)
fix_upgrade = _migration_module.upgrade
fix_downgrade = _migration_module.downgrade


@pytest.fixture
def db_session():
    """创建内存数据库会话并插入旧版 MoviePilot 数据。"""
    engine = create_engine("sqlite:///:memory:")
    App.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    app = App(
        name="moviepilot",
        display_name="MoviePilot",
        category="movie",
        config_schema={
            "type": "object",
            "properties": {
                "ports": {"type": "array"},
                "volumes": {"type": "array"},
                "moviepilot_env": {"type": "array"},
                "postgresql_env": {
                    "type": "array",
                    "default": [{"key": "POSTGRES_PASSWORD", "value": ""}],
                },
                "redis_env": {
                    "type": "array",
                    "default": [{"key": "REDIS_PASSWORD", "value": ""}],
                },
            },
            "required": [
                "ports",
                "volumes",
                "moviepilot_env",
                "postgresql_env",
                "redis_env",
            ],
            "containers": [
                {
                    "name": "moviepilot",
                    "title": "MoviePilot",
                    "settings": [
                        {"type": "ports", "title": "端口设置", "fields": ["ports"]},
                        {"type": "volumes", "title": "存储空间设置", "fields": ["volumes"]},
                        {"type": "env", "title": "环境变量", "fields": ["moviepilot_env"]},
                    ],
                },
                {
                    "name": "redis",
                    "title": "Redis",
                    "description": "Redis 缓存服务",
                    "settings": [
                        {"type": "env", "title": "环境变量", "fields": ["redis_env"]},
                    ],
                },
                {
                    "name": "postgresql",
                    "title": "PostgreSQL",
                    "description": "PostgreSQL 数据库服务",
                    "settings": [
                        {"type": "env", "title": "环境变量", "fields": ["postgresql_env"]},
                    ],
                },
            ],
        },
        yaml_template="""services:
  moviepilot:
    environment:
      - DB_POSTGRESQL_PASSWORD={{ postgresql_env[0].value }}
      - CACHE_BACKEND_URL=redis://:{{ redis_env[0].value }}@redis:6379
  redis:
    environment:
{%- for item in redis_env %}
      - {{ item.key }}={{ item.value }}
{%- endfor %}
    command: redis-server --requirepass ${REDIS_PASSWORD}
  postgresql:
    environment:
      POSTGRES_DB: moviepilot
{%- for item in postgresql_env %}
      {{ item.key }}: {{ item.value }}
{%- endfor %}
""",
        type="compose",
        is_builtin=True,
    )
    session.add(app)
    session.commit()

    yield session

    session.close()
    engine.dispose()


def test_upgrade_uses_jinja_lookup_not_hardcoded_index(db_session):
    """升级后模板使用 selectattr 查找，不再硬编码数组索引。"""
    mock_op = MagicMock()
    mock_op.get_bind.return_value = db_session.bind

    with patch.object(_migration_module, "op", mock_op):
        fix_upgrade()

    db_session.expire_all()
    app = db_session.query(App).filter_by(name="moviepilot").one()

    assert "selectattr('key', 'equalto', 'REDIS_PASSWORD')" in app.yaml_template
    assert "selectattr('key', 'equalto', 'POSTGRES_PASSWORD')" in app.yaml_template
    assert "redis_env[0].value" not in app.yaml_template
    assert "postgresql_env[0].value" not in app.yaml_template


def test_downgrade_restores_hardcoded_index_template(db_session):
    """降级后恢复为硬编码数组索引的模板。"""
    mock_op = MagicMock()
    mock_op.get_bind.return_value = db_session.bind

    with patch.object(_migration_module, "op", mock_op):
        fix_upgrade()
        fix_downgrade()

    db_session.expire_all()
    app = db_session.query(App).filter_by(name="moviepilot").one()

    assert "{{ postgresql_env[0].value }}" in app.yaml_template
    assert "{{ redis_env[0].value }}" in app.yaml_template
    assert "selectattr" not in app.yaml_template


def test_upgrade_does_not_change_config_schema(db_session):
    """升级不改 config_schema，密码仍在各自容器下维护。"""
    mock_op = MagicMock()
    mock_op.get_bind.return_value = db_session.bind

    with patch.object(_migration_module, "op", mock_op):
        fix_upgrade()

    db_session.expire_all()
    app = db_session.query(App).filter_by(name="moviepilot").one()
    schema = app.config_schema

    assert "redis_env" in schema["properties"]
    assert "postgresql_env" in schema["properties"]
    assert "redis_password" not in schema["properties"]
    assert "pg_password" not in schema["properties"]
