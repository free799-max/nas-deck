"""fix moviepilot shared passwords

Revision ID: d552fb162f5c
Revises: 575516511862
Create Date: 2026-06-22 16:02:39.881684

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

import app.models  # noqa: F401
from app.models.app_store import App


# revision identifiers, used by Alembic.
revision: str = 'd552fb162f5c'
down_revision: Union[str, None] = '575516511862'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 从环境变量数组中按 key 查找 value 的 Jinja2 辅助表达式
_LOOKUP_REDIS = (
    "(redis_env | selectattr('key', 'equalto', 'REDIS_PASSWORD') | map(attribute='value') | first | default(''))"
)
_LOOKUP_PG = (
    "(postgresql_env | selectattr('key', 'equalto', 'POSTGRES_PASSWORD') | map(attribute='value') | first | default(''))"
)


def upgrade() -> None:
    """修正 MoviePilot 模板中跨服务密码引用，避免硬编码数组索引。"""
    bind = op.get_bind()
    session = Session(bind=bind)

    app = session.execute(
        select(App).where(App.name == 'moviepilot')
    ).scalar_one_or_none()

    if app is None:
        return

    # 本次迁移只改 yaml_template，config_schema 保持 redis_env / postgresql_env 数组不变
    app.yaml_template = f"""services:
  moviepilot:
    stdin_open: true
    tty: true
    container_name: moviepilot-v2
    hostname: moviepilot-v2
    ports:
{{%- for port in ports %}}
      - "{{{{ port.local_port }}}}:{{{{ port.container_port }}}}/{{{{ port.protocol }}}}"
{{%- endfor %}}
    volumes:
{{%- for vol in volumes %}}
      - {{{{ vol.host_path }}}}:{{{{ vol.container_path }}}}:{{{{ vol.mode }}}}
{{%- endfor %}}
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
{{%- for item in moviepilot_env %}}
      - {{{{ item.key }}}}={{{{ item.value }}}}
{{%- endfor %}}
      - DB_TYPE=postgresql
      - DB_POSTGRESQL_HOST=postgresql
      - DB_POSTGRESQL_PORT=5432
      - DB_POSTGRESQL_DATABASE=moviepilot
      - DB_POSTGRESQL_USERNAME=moviepilot
      - DB_POSTGRESQL_PASSWORD={{{{ {_LOOKUP_PG} }}}}
      - CACHE_BACKEND_TYPE=redis
      - CACHE_BACKEND_URL=redis://:{{{{ {_LOOKUP_REDIS} }}}}@redis:6379
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
{{%- for item in redis_env %}}
      - {{{{ item.key }}}}={{{{ item.value }}}}
{{%- endfor %}}
    command: redis-server --save 600 1 --requirepass {{{{ {_LOOKUP_REDIS} }}}}
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
{{%- for item in postgresql_env %}}
      {{{{ item.key }}}}: {{{{ item.value }}}}
{{%- endfor %}}
    volumes:
      - /volume1/docker/postgresql:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U moviepilot -d moviepilot"]
      interval: 10s
      timeout: 5s
      retries: 5
"""

    flag_modified(app, 'yaml_template')
    session.commit()


def downgrade() -> None:
    """回滚为硬编码数组索引的模板。"""
    bind = op.get_bind()
    session = Session(bind=bind)

    app = session.execute(
        select(App).where(App.name == 'moviepilot')
    ).scalar_one_or_none()

    if app is None:
        return

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

    flag_modified(app, 'yaml_template')
    session.commit()
