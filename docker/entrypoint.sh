#!/usr/bin/env bash
set -Eeuo pipefail

api_pid=""
web_pid=""

shutdown() {
    trap - TERM INT
    if [[ -n "$api_pid" ]]; then
        kill -TERM "$api_pid" 2>/dev/null || true
    fi
    if [[ -n "$web_pid" ]]; then
        kill -TERM "$web_pid" 2>/dev/null || true
    fi
    wait 2>/dev/null || true
}

trap 'shutdown; exit 143' TERM INT

# 后端只监听容器内回环地址，所有外部请求统一由 Nginx 进入。
uvicorn app.main:app \
    --host 127.0.0.1 \
    --port 5001 \
    --proxy-headers \
    --no-access-log &
api_pid=$!

nginx -g 'daemon off;' &
web_pid=$!

# 任一进程退出即停止另一个，避免容器带病运行；退出码交给 Docker 重启策略处理。
set +e
wait -n "$api_pid" "$web_pid"
status=$?
set -e

shutdown
exit "$status"
