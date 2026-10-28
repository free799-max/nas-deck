# syntax=docker/dockerfile:1

# 基础镜像复用：CI 先构建并推送 base 阶段到 Harbor，再通过
# --build-arg BASE_IMAGE=<registry>/<project>/nas-deck-base:<tag> 直接复用，
# 不必每次从系统依赖装起。本地构建不传该参数，默认使用下文的 base 阶段。
ARG BASE_IMAGE=base

# 1. 提供 docker / docker compose CLI，供应用通过挂载的 docker.sock 管理宿主机容器
FROM docker:27-cli AS docker-cli

# 2. 基础层：系统依赖、Docker CLI 与 Python 依赖。变化频率低，由 CI 单独构建并推送
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 默认使用国内镜像源；海外环境可通过 --build-arg 覆盖
ARG DEBIAN_MIRROR=https://mirrors.aliyun.com
RUN sed -i "s|http://deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends nginx tzdata \
    && rm -rf /var/lib/apt/lists/* /etc/nginx/sites-enabled/default

WORKDIR /app
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins

ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
COPY backend/requirements.txt ./
RUN pip install --index-url "${PIP_INDEX_URL}" -r requirements.txt

# 3. 构建前端静态文件
FROM node:22-alpine AS frontend-build

WORKDIR /build
RUN npm install --global pnpm@10
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

# 4. 运行镜像：base + 后端代码 + 前端产物，Nginx 对外提供前端与 /api 反代
#    FastAPI 仅监听回环地址
FROM ${BASE_IMAGE} AS runtime

# 应用市场管理端地址：构建期写入镜像作为默认值，运行时由 .env 覆盖。
# CI 通过 --build-arg 传入，未传时使用生产地址。
ARG MANAGE_BASE_URL=https://deck-m.freeapps.uk
ENV MANAGE_BASE_URL=${MANAGE_BASE_URL}

# 只复制运行时文件，避免把本地的 backend/data、测试和虚拟环境带进镜像
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY --from=frontend-build /build/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/entrypoint.sh /usr/local/bin/nas-deck-entrypoint
RUN chmod +x /usr/local/bin/nas-deck-entrypoint \
    && mkdir -p /data

EXPOSE 80
STOPSIGNAL SIGTERM
ENTRYPOINT ["/usr/local/bin/nas-deck-entrypoint"]
