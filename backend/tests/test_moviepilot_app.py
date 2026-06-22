"""MoviePilot 应用商店模板渲染测试。"""

import yaml
import pytest

from app.services.app_store.app_service import _render_yaml_template


SAMPLE_MOVIEPILOT_SCHEMA = {
    "type": "object",
    "properties": {
        "moviepilot_env": {
            "type": "array",
            "default": [
                {"key": "SUPERUSER", "value": "admin"},
                {"key": "SUPERUSER_PASSWORD", "value": ""},
            ],
        },
        "redis_env": {
            "type": "array",
            "default": [{"key": "REDIS_PASSWORD", "value": ""}],
        },
        "postgresql_env": {
            "type": "array",
            "default": [{"key": "POSTGRES_PASSWORD", "value": ""}],
        },
    },
}

# 使用 Jinja2 selectattr 从各自容器的环境变量数组中查找密码值
SAMPLE_MOVIEPILOT_TEMPLATE = """services:
  moviepilot:
    environment:
{%- for item in moviepilot_env %}
      - {{ item.key }}={{ item.value }}
{%- endfor %}
      - DB_POSTGRESQL_PASSWORD={{ (postgresql_env | selectattr('key', 'equalto', 'POSTGRES_PASSWORD') | map(attribute='value') | first | default('')) }}
      - CACHE_BACKEND_URL=redis://:{{ (redis_env | selectattr('key', 'equalto', 'REDIS_PASSWORD') | map(attribute='value') | first | default('')) }}@redis:6379

  redis:
    environment:
{%- for item in redis_env %}
      - {{ item.key }}={{ item.value }}
{%- endfor %}
    command: redis-server --save 600 1 --requirepass {{ (redis_env | selectattr('key', 'equalto', 'REDIS_PASSWORD') | map(attribute='value') | first | default('')) }}

  postgresql:
    environment:
      POSTGRES_DB: moviepilot
      POSTGRES_USER: moviepilot
{%- for item in postgresql_env %}
      {{ item.key }}: {{ item.value }}
{%- endfor %}
"""


@pytest.fixture
def sample_config():
    return {
        "moviepilot_env": [
            {"key": "SUPERUSER", "value": "admin"},
            {"key": "SUPERUSER_PASSWORD", "value": "admin123"},
        ],
        "redis_env": [{"key": "REDIS_PASSWORD", "value": "myredispass"}],
        "postgresql_env": [{"key": "POSTGRES_PASSWORD", "value": "mypgpass"}],
    }


def test_render_moviepilot_shared_passwords(sample_config):
    """共享密码通过 Jinja2 查找从各自容器数组中取值并多处引用。"""
    rendered = _render_yaml_template(
        SAMPLE_MOVIEPILOT_TEMPLATE,
        SAMPLE_MOVIEPILOT_SCHEMA,
        sample_config,
        project_name="moviepilot-test",
    )

    parsed = yaml.safe_load(rendered)

    moviepilot_env = parsed["services"]["moviepilot"]["environment"]
    assert "DB_POSTGRESQL_PASSWORD=mypgpass" in moviepilot_env
    assert "CACHE_BACKEND_URL=redis://:myredispass@redis:6379" in moviepilot_env

    redis = parsed["services"]["redis"]
    assert "REDIS_PASSWORD=myredispass" in redis["environment"]
    assert "--requirepass myredispass" in redis["command"]

    postgresql = parsed["services"]["postgresql"]
    assert postgresql["environment"]["POSTGRES_PASSWORD"] == "mypgpass"


def test_render_moviepilot_uses_schema_defaults():
    """未提供的字段使用 schema 默认值渲染。"""
    rendered = _render_yaml_template(
        SAMPLE_MOVIEPILOT_TEMPLATE,
        SAMPLE_MOVIEPILOT_SCHEMA,
        {},
        project_name="moviepilot-test",
    )

    parsed = yaml.safe_load(rendered)

    moviepilot_env = parsed["services"]["moviepilot"]["environment"]
    assert "DB_POSTGRESQL_PASSWORD=" in moviepilot_env
    assert "CACHE_BACKEND_URL=redis://:@redis:6379" in moviepilot_env


def test_render_moviepilot_lookup_by_key_not_index():
    """即使密码不是数组第一项，也能按 key 正确查找。"""
    config = {
        "redis_env": [
            {"key": "SOME_OTHER_VAR", "value": "x"},
            {"key": "REDIS_PASSWORD", "value": "myredispass"},
        ],
        "postgresql_env": [
            {"key": "SOME_OTHER_VAR", "value": "y"},
            {"key": "POSTGRES_PASSWORD", "value": "mypgpass"},
        ],
    }

    rendered = _render_yaml_template(
        SAMPLE_MOVIEPILOT_TEMPLATE,
        SAMPLE_MOVIEPILOT_SCHEMA,
        config,
        project_name="moviepilot-test",
    )

    parsed = yaml.safe_load(rendered)
    moviepilot_env = parsed["services"]["moviepilot"]["environment"]
    assert "DB_POSTGRESQL_PASSWORD=mypgpass" in moviepilot_env
    assert "CACHE_BACKEND_URL=redis://:myredispass@redis:6379" in moviepilot_env
