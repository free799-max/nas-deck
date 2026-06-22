"""update moviepilot env schema

Revision ID: 575516511862
Revises: 62a6a8d901e6
Create Date: 2026-06-22 11:29:20.045207

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

import app.models  # noqa: F401
from app.models.app_store import App


# revision identifiers, used by Alembic.
revision: str = '575516511862'
down_revision: Union[str, None] = '62a6a8d901e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """将 MoviePilot 的 PostgreSQL/Redis 密码字段改为环境变量数组格式。"""
    bind = op.get_bind()
    session = Session(bind=bind)

    app = session.execute(
        select(App).where(App.name == 'moviepilot')
    ).scalar_one_or_none()

    if app is None:
        return

    schema = app.config_schema or {}
    properties = schema.get('properties', {})

    # 1. 替换 pg_password / redis_password 为数组格式
    if 'pg_password' in properties:
        del properties['pg_password']
    if 'redis_password' in properties:
        del properties['redis_password']

    properties['postgresql_env'] = {
        'type': 'array',
        'title': '环境变量',
        'items': {
            'type': 'object',
            'properties': {
                'key': {'type': 'string', 'title': '变量名'},
                'value': {'type': 'string', 'title': '值'},
            },
            'required': ['key', 'value'],
        },
        'default': [{'key': 'POSTGRES_PASSWORD', 'value': ''}],
    }
    properties['redis_env'] = {
        'type': 'array',
        'title': '环境变量',
        'items': {
            'type': 'object',
            'properties': {
                'key': {'type': 'string', 'title': '变量名'},
                'value': {'type': 'string', 'title': '值'},
            },
            'required': ['key', 'value'],
        },
        'default': [{'key': 'REDIS_PASSWORD', 'value': ''}],
    }

    # 2. 更新 required
    schema['required'] = [
        'ports',
        'volumes',
        'moviepilot_env',
        'postgresql_env',
        'redis_env',
    ]

    # 3. 更新 containers 中对应的 fields
    for container in schema.get('containers', []):
        for setting in container.get('settings', []):
            if setting.get('type') == 'env':
                if container.get('name') == 'redis':
                    setting['fields'] = ['redis_env']
                elif container.get('name') == 'postgresql':
                    setting['fields'] = ['postgresql_env']

    app.config_schema = schema
    flag_modified(app, 'config_schema')

    # 4. 更新 yaml_template
    app.yaml_template = """services:
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
"""

    session.commit()


def downgrade() -> None:
    """Rollback is not supported for this data migration."""
    pass
