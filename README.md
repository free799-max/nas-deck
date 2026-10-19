# NasDeck

NAS 管理平台：Docker 容器/镜像/Compose Stack 管理、应用商店（内置 NAS 应用模板一键部署）、自动化编排与看板视图。前后端分离，支持 docker compose 一键部署。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12 + FastAPI + SQLAlchemy 2.0（异步）|
| 数据库 | PostgreSQL 16（asyncpg 异步驱动）+ Alembic 迁移 |
| 前端 | React 19 + TypeScript + Vite + Tailwind CSS + shadcn/ui（pnpm 管理）|
| 认证 | JWT Bearer Token + bcrypt（首个注册用户自动成为管理员）|
| 部署 | Docker + docker compose（前端 nginx 静态托管并反代 /api）|

## Docker Compose 部署（推荐）

环境要求：Docker 与 Docker Compose v2.24+。

```bash
git clone <仓库地址>
cd nas-deck

# 复制环境变量模板，至少修改 POSTGRES_PASSWORD 与 SECRET_KEY
cp .env.example .env
$EDITOR .env

# 构建并启动全部服务（postgres + backend + frontend）
docker compose up --build -d
```

- 前端入口：`http://localhost:5000`
- 后端 API：`http://localhost:5001`（文档见 `/docs`）
- 数据持久化：PostgreSQL 使用命名卷 `postgres_data`；应用数据（Compose 工作区、图标等）映射到 `./data/`
- 首次启动自动执行数据库迁移；访问前端注册首个账号即为管理员

> 说明：compose 中挂载了 `/var/run/docker.sock` 以提供容器/Compose 管理功能，等同于授予容器宿主机 root 权限，请仅在受信环境使用；不需要时可删除该挂载（相关功能自动降级）。

## 本地开发（Linux）

### 后端（`backend/`）

```bash
# 启动 PostgreSQL（如未运行，映射宿主机 5434 端口）
docker run -d --name nasdeck-db -e POSTGRES_USER=nasdeck \
  -e POSTGRES_PASSWORD=nasdeck -e POSTGRES_DB=nasdeck \
  -p 5434:5432 postgres:16-alpine

cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 启动开发服务器（http://localhost:5001）
PYTHONPATH=./app .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 5001

# 测试与数据库迁移
PYTHONPATH=./app .venv/bin/python -m pytest
PYTHONPATH=./app .venv/bin/python -m alembic upgrade head
```

### 前端（`frontend/`，pnpm）

```bash
cd frontend
pnpm install
pnpm run dev      # 开发服务器 http://localhost:5000，代理 /api -> localhost:5001
pnpm run build    # TypeScript 编译 + Vite 构建
pnpm run lint     # ESLint 检查
```

> 另提供 pm2 本机开发备选方案（`ecosystem.config.js` + `start-backend.sh`），正式部署请使用 docker compose。

## 目录结构

```
nas-deck/
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── api/            # 路由层（auth/orchestrations/app_store/deploy_tasks/settings/docker）
│   │   ├── services/       # 业务层（docker/compose/orchestration/apps/app_store/host）
│   │   ├── models/         # SQLAlchemy ORM 模型
│   │   ├── schemas/        # Pydantic 请求/响应模型
│   │   └── main.py         # FastAPI 入口（lifespan 自动执行迁移）
│   ├── alembic/            # 数据库迁移
│   └── tests/              # pytest 测试套件
├── frontend/               # React + Vite 前端
│   ├── src/api/            # 后端请求的唯一封装入口（与后端 schema 对齐）
│   ├── src/pages/          # 页面（dashboard/apps/automation/docker/settings/auth）
│   └── nginx.conf          # 生产环境 nginx 配置（反代 /api）
├── docs/                   # 设计文档与 API 规范
├── docker-compose.yml      # postgres + backend + frontend 一键部署
└── .env.example            # 环境变量模板
```

## 更多文档

- [CLAUDE.md](CLAUDE.md)：架构分层、开发约定、异步部署任务（SSE）、应用商店维护等开发细节
- [docs/整体架构设计.md](docs/整体架构设计.md)：整体架构设计
- [docs/api/api-response-spec.md](docs/api/api-response-spec.md)：API 统一响应格式规范
