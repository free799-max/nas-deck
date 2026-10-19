#!/bin/bash
# 本机开发备选方案（配合 pm2，见 ecosystem.config.js）：正式部署请使用 docker-compose（见 README.md）。
# 依赖 backend/.venv 虚拟环境，首次使用请先执行：cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
set -e

BACKEND_DIR="$(cd "$(dirname "$0")/backend" && pwd)"
export PYTHONPATH="$BACKEND_DIR"

cd "$BACKEND_DIR"
"$BACKEND_DIR/.venv/bin/python" -m alembic upgrade head
exec "$BACKEND_DIR/.venv/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 5001 --lifespan off
