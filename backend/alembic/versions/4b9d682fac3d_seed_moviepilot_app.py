"""seed moviepilot app

Revision ID: 4b9d682fac3d
Revises: 702a6bd8273a
Create Date: 2026-06-19 20:44:24.380685

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import MetaData, Table, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.models.app_store import App


def _reflect_table(table_name: str) -> Table:
    """反射当前数据库中的表结构，兼容 ORM 模型与表结构不同步的情况。"""
    metadata = MetaData()
    return Table(table_name, metadata, autoload_with=op.get_bind())


# revision identifiers, used by Alembic.
revision: str = '4b9d682fac3d'
down_revision: Union[str, None] = '702a6bd8273a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BUILTIN_APPS: list[dict] = [
    {
        'name': 'moviepilot',
        'display_name': 'MoviePilot',
        'description': '',
        'category': 'movie',
        'tags': ['影视'],
        'icon': None,
        'website': 'https://movie-pilot.org/',
        'source_url': 'https://github.com/jxxghp/MoviePilot',
        'architectures': ['amd64', 'arm64'],
        'image': 'jxxghp/moviepilot-v2:latest',
        'default_ports': [
            {'port': 3000, 'protocol': 'tcp', 'description': 'MoviePilot Web UI'},
            {'port': 3001, 'protocol': 'tcp', 'description': 'MoviePilot API'},
        ],
        'config_schema': {
            'type': 'object',
            'properties': {
                'ports': {
                    'type': 'array',
                    'title': '端口设置',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'local_port': {
                                'type': 'integer',
                                'title': '本地端口',
                                'minimum': 1,
                                'maximum': 65535,
                            },
                            'container_port': {
                                'type': 'integer',
                                'title': '容器端口',
                                'minimum': 1,
                                'maximum': 65535,
                            },
                            'protocol': {
                                'type': 'string',
                                'title': '协议',
                                'enum': ['tcp', 'udp'],
                                'default': 'tcp',
                            },
                        },
                        'required': ['local_port', 'container_port', 'protocol'],
                    },
                    'default': [
                        {'local_port': 3000, 'container_port': 3000, 'protocol': 'tcp'},
                        {'local_port': 3001, 'container_port': 3001, 'protocol': 'tcp'},
                    ],
                },
                'volumes': {
                    'type': 'array',
                    'title': '存储空间设置',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'host_path': {
                                'type': 'string',
                                'title': '本地路径',
                            },
                            'container_path': {
                                'type': 'string',
                                'title': '容器路径',
                            },
                            'mode': {
                                'type': 'string',
                                'title': '权限',
                                'enum': ['rw', 'ro'],
                                'default': 'rw',
                            },
                        },
                        'required': ['host_path', 'container_path', 'mode'],
                    },
                    'default': [
                        {'host_path': '/media', 'container_path': '/media', 'mode': 'rw'},
                        {'host_path': '/moviepilot-v2/config', 'container_path': '/config', 'mode': 'rw'},
                    ],
                },
                'moviepilot_env': {
                    'type': 'array',
                    'title': '环境变量',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'key': {
                                'type': 'string',
                                'title': '变量名',
                            },
                            'value': {
                                'type': 'string',
                                'title': '值',
                            },
                        },
                        'required': ['key', 'value'],
                    },
                    'default': [
                        {'key': 'SUPERUSER', 'value': 'admin'},
                        {'key': 'SUPERUSER_PASSWORD', 'value': ''},
                    ],
                },
                'postgresql_env': {
                    'type': 'array',
                    'title': '环境变量',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'key': {
                                'type': 'string',
                                'title': '变量名',
                            },
                            'value': {
                                'type': 'string',
                                'title': '值',
                            },
                        },
                        'required': ['key', 'value'],
                    },
                    'default': [
                        {'key': 'POSTGRES_PASSWORD', 'value': ''},
                    ],
                },
                'redis_env': {
                    'type': 'array',
                    'title': '环境变量',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'key': {
                                'type': 'string',
                                'title': '变量名',
                            },
                            'value': {
                                'type': 'string',
                                'title': '值',
                            },
                        },
                        'required': ['key', 'value'],
                    },
                    'default': [
                        {'key': 'REDIS_PASSWORD', 'value': ''},
                    ],
                },
            },
            'required': [
                'ports',
                'volumes',
                'moviepilot_env',
                'postgresql_env',
                'redis_env',
            ],
            'containers': [
                {
                    'name': 'moviepilot',
                    'title': 'MoviePilot',
                    'description': 'MoviePilot 主服务',
                    'settings': [
                        {
                            'type': 'ports',
                            'title': '端口设置',
                            'fields': [
                                'ports',
                            ],
                        },
                        {
                            'type': 'volumes',
                            'title': '存储空间设置',
                            'fields': [
                                'volumes',
                            ],
                        },
                        {
                            'type': 'env',
                            'title': '环境变量',
                            'fields': [
                                'moviepilot_env',
                            ],
                        },
                    ],
                },
                {
                    'name': 'redis',
                    'title': 'Redis',
                    'description': 'Redis 缓存服务',
                    'settings': [
                        {
                            'type': 'env',
                            'title': '环境变量',
                            'fields': [
                                'redis_env',
                            ],
                        },
                    ],
                },
                {
                    'name': 'postgresql',
                    'title': 'PostgreSQL',
                    'description': 'PostgreSQL 数据库服务',
                    'settings': [
                        {
                            'type': 'env',
                            'title': '环境变量',
                            'fields': [
                                'postgresql_env',
                            ],
                        },
                    ],
                },
            ],
        },
        'yaml_template': """services:
  moviepilot:
    stdin_open: true
    tty: true
    container_name: moviepilot-v2
    hostname: moviepilot-v2
    ports:
{%- for port in ports %}
      - "{{ port.local_port }}:{{ port.container_port }}/{{ port.protocol }}"
{%- endfor %}
    volumes:
{%- for vol in volumes %}
      - {{ vol.host_path }}:{{ vol.container_path }}:{{ vol.mode }}
{%- endfor %}
      - /moviepilot-v2/core:/moviepilot/.cloakbrowser
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /tr/config/torrents:/torrents
      - /qbittorrent/data/data/BT_backup:/BT_backup
    environment:
      - NGINX_PORT=3000
      - PORT=3001
      - PUID=0
      - PGID=0
      - UMASK=000
      - TZ=Asia/Shanghai
{%- for item in moviepilot_env %}
      - {{ item.key }}={{ item.value }}
{%- endfor %}
      - DB_TYPE=postgresql
      - DB_POSTGRESQL_HOST=postgresql
      - DB_POSTGRESQL_PORT=5432
      - DB_POSTGRESQL_DATABASE=moviepilot
      - DB_POSTGRESQL_USERNAME=moviepilot
      - DB_POSTGRESQL_PASSWORD={{ postgresql_env[0].value }}
      - CACHE_BACKEND_TYPE=redis
      - CACHE_BACKEND_URL=redis://:{{ redis_env[0].value }}@redis:6379
    restart: always
    depends_on:
      postgresql:
        condition: service_healthy
      redis:
        condition: service_healthy
    image: jxxghp/moviepilot-v2:latest

  redis:
    image: redis
    volumes:
      - /volume1/docker/redis/data:/data
    environment:
{%- for item in redis_env %}
      - {{ item.key }}={{ item.value }}
{%- endfor %}
    command: redis-server --save 600 1 --requirepass ${REDIS_PASSWORD}
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  postgresql:
    image: postgres
    restart: always
    environment:
      POSTGRES_DB: moviepilot
      POSTGRES_USER: moviepilot
{%- for item in postgresql_env %}
      {{ item.key }}: {{ item.value }}
{%- endfor %}
    volumes:
      - /volume1/docker/postgresql:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U moviepilot -d moviepilot"]
      interval: 10s
      timeout: 5s
      retries: 5
""",
        'readme': """## 主要功能

- **智能搜索与订阅**：自动搜索和匹配电影、电视剧，智能订阅管理。
- **自动下载管理**：根据用户设定的规则自动下载资源，支持 qBittorrent、Transmission 等主流下载客户端。
- **智能重命名整理**：自动重命名和整理媒体文件，支持自定义命名格式，确保媒体库结构清晰有序。
- **媒体服务器集成**：无缝集成 Plex、Emby、Jellyfin 等主流媒体服务器，自动刷新媒体库。
- **多样化通知系统**：支持微信、Telegram、Slack 等多种通知方式，及时了解整理进度和系统状态。
- **内置智能助手**：支持自然语言甚至语音控制自动化管理，直接下达搜索、订阅、下载、整理等操作指令，让常用流程更省心。
""",
        'version': '1.0.0',
        'type': 'compose',
        'changelog': None,
        'backup_paths': [
            '/moviepilot-v2/config',
            '/volume1/docker/postgresql',
        ],
        'source_dir': None,
        'is_builtin': True,
    },
]


def upgrade() -> None:
    """Seed MoviePilot app into app store."""
    bind = op.get_bind()
    session = Session(bind=bind)

    # 反射当前 apps 表结构，兼容 default_values 被删除前的旧表
    table = _reflect_table("apps")
    columns = {col.name for col in table.columns}

    for data in BUILTIN_APPS:
        existing = session.execute(
            select(App).where(App.name == data["name"])
        ).scalar_one_or_none()
        if existing is None:
            app_data = dict(data)
            if "default_values" in columns:
                app_data["default_values"] = {}
            # 过滤掉当前表不存在的字段
            app_data = {k: v for k, v in app_data.items() if k in columns}
            session.execute(table.insert().values(app_data))
        elif existing.is_builtin:
            for key, value in data.items():
                if key in columns:
                    setattr(existing, key, value)

    session.commit()


def downgrade() -> None:
    """Remove MoviePilot app seeded by this migration."""
    bind = op.get_bind()
    session = Session(bind=bind)

    app_names = [data["name"] for data in BUILTIN_APPS]
    session.execute(
        App.__table__.delete().where(App.name.in_(app_names))
    )
    session.commit()
