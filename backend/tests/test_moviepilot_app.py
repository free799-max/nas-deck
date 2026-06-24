"""MoviePilot 应用商店模板渲染测试。"""

import yaml
import pytest

from app.services.app_store.app_service import _render_yaml_template
from app.services.system_config_service import StoragePathResolver


SAMPLE_MOVIEPILOT_SCHEMA = {
    "type": "object",
    "properties": {
        "moviepilot_volumes": {
            "type": "array",
            "default": [
                {"host_path": "moviepilot/config", "container_path": "/config", "mode": "rw"},
                {"host_path": "moviepilot/core", "container_path": "/moviepilot/.cloakbrowser", "mode": "rw"},
            ],
        },
        "redis_volumes": {
            "type": "array",
            "default": [{"host_path": "redis/data", "container_path": "/data", "mode": "rw"}],
        },
        "postgresql_volumes": {
            "type": "array",
            "default": [{"host_path": "postgresql/data", "container_path": "/var/lib/postgresql", "mode": "rw"}],
        },
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
    container_name: {{ project_name }}
    hostname: {{ project_name }}
    volumes:
{%- for vol in moviepilot_volumes %}
      - {{ to_host_path(vol.host_path if vol.host_path.startswith('/') else project_name ~ '/' ~ vol.host_path) }}:{{ vol.container_path }}:{{ vol.mode }}
{%- endfor %}
    environment:
{%- for item in moviepilot_env %}
      - {{ item.key }}={{ item.value }}
{%- endfor %}
      - DB_POSTGRESQL_PASSWORD={{ (postgresql_env | selectattr('key', 'equalto', 'POSTGRES_PASSWORD') | map(attribute='value') | first | default('')) }}
      - CACHE_BACKEND_URL=redis://:{{ (redis_env | selectattr('key', 'equalto', 'REDIS_PASSWORD') | map(attribute='value') | first | default('')) }}@redis:6379

  redis:
    image: redis
    container_name: {{ project_name }}-redis
    volumes:
{%- for vol in redis_volumes %}
      - {{ to_host_path(vol.host_path if vol.host_path.startswith('/') else project_name ~ '/' ~ vol.host_path) }}:{{ vol.container_path }}:{{ vol.mode }}
{%- endfor %}
    environment:
{%- for item in redis_env %}
      - {{ item.key }}={{ item.value }}
{%- endfor %}
    command: redis-server --save 600 1 --requirepass {{ (redis_env | selectattr('key', 'equalto', 'REDIS_PASSWORD') | map(attribute='value') | first | default('')) }}

  postgresql:
    image: postgres
    container_name: {{ project_name }}-postgresql
    environment:
      POSTGRES_DB: moviepilot
      POSTGRES_USER: moviepilot
{%- for item in postgresql_env %}
      {{ item.key }}: {{ item.value }}
{%- endfor %}
    volumes:
{%- for vol in postgresql_volumes %}
      - {{ to_host_path(vol.host_path if vol.host_path.startswith('/') else project_name ~ '/' ~ vol.host_path) }}:{{ vol.container_path }}:{{ vol.mode }}
{%- endfor %}
"""


@pytest.fixture
def sample_config():
    return {
        "moviepilot_volumes": [
            {"host_path": "moviepilot/config", "container_path": "/config", "mode": "rw"},
            {"host_path": "moviepilot/core", "container_path": "/moviepilot/.cloakbrowser", "mode": "rw"},
        ],
        "redis_volumes": [{"host_path": "redis/data", "container_path": "/data", "mode": "rw"}],
        "postgresql_volumes": [{"host_path": "postgresql/data", "container_path": "/var/lib/postgresql", "mode": "rw"}],
        "moviepilot_env": [
            {"key": "SUPERUSER", "value": "admin"},
            {"key": "SUPERUSER_PASSWORD", "value": "admin123"},
        ],
        "redis_env": [{"key": "REDIS_PASSWORD", "value": "myredispass"}],
        "postgresql_env": [{"key": "POSTGRES_PASSWORD", "value": "mypgpass"}],
    }


@pytest.fixture
def resolver():
    return StoragePathResolver(None, None).with_defaults()


def test_render_moviepilot_shared_passwords(sample_config, resolver):
    """共享密码通过 Jinja2 查找从各自容器数组中取值并多处引用。"""
    rendered = _render_yaml_template(
        SAMPLE_MOVIEPILOT_TEMPLATE,
        SAMPLE_MOVIEPILOT_SCHEMA,
        sample_config,
        project_name="moviepilot-test",
        resolver=resolver,
    )

    parsed = yaml.safe_load(rendered)

    moviepilot = parsed["services"]["moviepilot"]
    assert moviepilot["container_name"] == "moviepilot-test"
    assert moviepilot["hostname"] == "moviepilot-test"

    moviepilot_env = moviepilot["environment"]
    assert "DB_POSTGRESQL_PASSWORD=mypgpass" in moviepilot_env
    assert "CACHE_BACKEND_URL=redis://:myredispass@redis:6379" in moviepilot_env

    redis = parsed["services"]["redis"]
    assert redis["container_name"] == "moviepilot-test-redis"
    assert "REDIS_PASSWORD=myredispass" in redis["environment"]
    assert "--requirepass myredispass" in redis["command"]

    postgresql = parsed["services"]["postgresql"]
    assert postgresql["container_name"] == "moviepilot-test-postgresql"
    assert postgresql["environment"]["POSTGRES_PASSWORD"] == "mypgpass"


def test_render_moviepilot_uses_schema_defaults(resolver):
    """未提供的字段使用 schema 默认值渲染。"""
    rendered = _render_yaml_template(
        SAMPLE_MOVIEPILOT_TEMPLATE,
        SAMPLE_MOVIEPILOT_SCHEMA,
        {},
        project_name="moviepilot-test",
        resolver=resolver,
    )

    parsed = yaml.safe_load(rendered)

    moviepilot_env = parsed["services"]["moviepilot"]["environment"]
    assert "DB_POSTGRESQL_PASSWORD=" in moviepilot_env
    assert "CACHE_BACKEND_URL=redis://:@redis:6379" in moviepilot_env


def test_render_moviepilot_lookup_by_key_not_index(resolver):
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
        resolver=resolver,
    )

    parsed = yaml.safe_load(rendered)
    moviepilot_env = parsed["services"]["moviepilot"]["environment"]
    assert "DB_POSTGRESQL_PASSWORD=mypgpass" in moviepilot_env
    assert "CACHE_BACKEND_URL=redis://:myredispass@redis:6379" in moviepilot_env


def test_render_moviepilot_isolates_volumes_by_project_name(resolver):
    """不同 project_name 的挂载路径彼此隔离。"""
    config = {
        "moviepilot_volumes": [
            {"host_path": "moviepilot/config", "container_path": "/config", "mode": "rw"},
        ],
        "redis_volumes": [{"host_path": "redis/data", "container_path": "/data", "mode": "rw"}],
        "postgresql_volumes": [{"host_path": "postgresql/data", "container_path": "/var/lib/postgresql", "mode": "rw"}],
    }

    rendered_a = _render_yaml_template(
        SAMPLE_MOVIEPILOT_TEMPLATE,
        SAMPLE_MOVIEPILOT_SCHEMA,
        config,
        project_name="moviepilot-a",
        resolver=resolver,
    )
    rendered_b = _render_yaml_template(
        SAMPLE_MOVIEPILOT_TEMPLATE,
        SAMPLE_MOVIEPILOT_SCHEMA,
        config,
        project_name="moviepilot-b",
        resolver=resolver,
    )

    parsed_a = yaml.safe_load(rendered_a)
    parsed_b = yaml.safe_load(rendered_b)

    vol_a = parsed_a["services"]["moviepilot"]["volumes"][0]
    vol_b = parsed_b["services"]["moviepilot"]["volumes"][0]

    assert "moviepilot-a/moviepilot/config" in vol_a
    assert "moviepilot-b/moviepilot/config" in vol_b
    assert vol_a != vol_b


def test_render_moviepilot_keeps_absolute_volume_path(resolver):
    """绝对路径的 host_path 不拼 project_name 前缀。"""
    config = {
        "moviepilot_volumes": [
            {"host_path": "/media", "container_path": "/media", "mode": "rw"},
        ],
    }

    rendered = _render_yaml_template(
        SAMPLE_MOVIEPILOT_TEMPLATE,
        SAMPLE_MOVIEPILOT_SCHEMA,
        config,
        project_name="moviepilot-test",
        resolver=resolver,
    )

    parsed = yaml.safe_load(rendered)
    vol = parsed["services"]["moviepilot"]["volumes"][0]

    assert vol == "/media:/media:rw"
