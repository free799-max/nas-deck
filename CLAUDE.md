# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

NasDeck — NAS 管理平台，提供 Docker 容器/镜像/Compose Stack 管理、应用商店（内置 NAS 应用模板）和看板视图。前后端分离，后端为 FastAPI + SQLAlchemy 异步服务。

## 开发命令

### 后端（在 `backend/` 目录下执行）

```bash
# 启动 PostgreSQL（如未运行）
docker run -d --name nasdeck-db -e POSTGRES_USER=nasdeck -e POSTGRES_PASSWORD=nasdeck -e POSTGRES_DB=nasdeck -p 5434:5432 postgres:16-alpine

# 启动开发服务器
cd backend
PYTHONPATH=./app .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 5001

# 运行全部测试
PYTHONPATH=./app .venv/bin/python -m pytest

# 运行单个测试文件
PYTHONPATH=./app .venv/bin/python -m pytest tests/test_docker_manager.py

# 运行单个测试函数
PYTHONPATH=./app .venv/bin/python -m pytest tests/test_docker_manager.py::test_list_containers -v

# 数据库迁移
PYTHONPATH=./app .venv/bin/python -m alembic upgrade head
```

> 注：Windows 环境请将 `.venv/bin/python` 替换为 `.venv/Scripts/python.exe`。

### 前端（`frontend/` 目录下）

```bash
npm run dev          # 开发服务器（端口 5000，代理 /api -> localhost:5001）
npm run build        # TypeScript 编译 + Vite 构建
npm run lint         # ESLint 检查
```

### Docker

```bash
docker-compose up --build   # 构建并启动前后端容器（后端 :5001，前端 :5000）
```

## 架构

### 请求生命周期

```
用户请求 -> Nginx(生产) / Vite Proxy(开发) -> FastAPI -> SQLAlchemy(异步) -> PostgreSQL
                                              |
                                              +-> JWT 认证(get_current_user 依赖注入)
                                              +-> CustomAPIRoute 自动包装 StandardResponse
                                              +-> services/ 业务层 -> Docker SDK / docker compose CLI
```

### 后端分层（`backend/app/`）

| 层 | 目录 | 职责 |
|---|---|---|
| 入口 | `main.py` | FastAPI 实例、lifespan（初始化DB）、CORS、路由注册、全局异常处理器 |
| 配置 | `config.py` | pydantic-settings，从 `.env` 加载（APP_NAME/DATABASE_URL/SECRET_KEY/ACCESS_TOKEN_EXPIRE_MINUTES/PLUGIN_DIR/COMPOSE_WORKSPACE_DIR） |
| 数据库 | `database.py` | SQLAlchemy 2.0 异步引擎(asyncpg/aiosqlite)、会话工厂、`get_db()` 依赖（自动 commit/rollback） |
| API | `api/` | 路由模块（auth/app_store/orchestrations/settings），Docker 路由按领域拆分为 `api/docker/` 子包，部署任务在 `api/orchestration/deploy_tasks.py` |
| 核心 | `core/` | 基础设施：security(JWT+bcrypt)、custom_route(响应包装)、exceptions。`docker_manager.py` 与 `compose_manager.py` 目前仅作为兼容入口保留 |
| 业务服务 | `services/` | 按功能域拆分：`docker/`（容器/镜像/宿主机/拉取任务）、`compose/`（Compose 编排/自动发现）、`orchestration/`（编排与部署任务）、`apps/`（应用客户端）、`app_store/`、`host/` |
| 初始化 | `initializers/` | 应用启动时的业务初始化，如默认 Docker Hub 镜像仓库配置 |
| 模型 | `models/` | SQLAlchemy ORM 模型；Docker 相关模型按领域拆分为 `models/docker/` 子包 |
| Schema | `schemas/` | Pydantic 请求/响应模型；Docker 相关 Schema 按领域拆分为 `schemas/docker/` 子包 |

### 前端分层（`frontend/src/`）

| 层 | 目录 | 职责 |
|---|---|---|
| 入口 | `App.tsx` | QueryClientProvider + AuthProvider + ToastProvider + BrowserRouter + ProtectedRoute |
| 布局 | `layouts/` | AppLayout(Sidebar+TopBar+Outlet)、Sidebar(导航)、TopBar |
| 页面 | `pages/` | 按功能域组织子目录：`auth/`、`dashboard/`(含 components/)、`apps/`、`automation/`(自动化编排)、`docker/`(含 containers/images/stacks/host/shared)、`settings/` |
| 数据 | `hooks/` | React Query hooks，只做缓存/状态/toast/SSE；**不定义接口类型、不直接拼 URL**，请求一律调用 `api/` 层函数，类型从 `api/` re-export 以兼容既有 import |
| API 封装 | `api/` | **所有后端请求的唯一入口**：按领域分文件（auth/apps/orchestrations/settings/directories/compose/docker），接口类型定义也在此，与后端 schemas 对齐只改这层。`types.ts` 导出共享 `ApiError` |
| HTTP 实例 | `lib/api.ts` | Axios 实例：请求拦截器附加 Bearer token；响应拦截器校验 `success` 标识后解包 `data`；401 时仅当请求 token 与本地一致才清除并跳转 /login（防竞态） |
| 工具 | `lib/utils.ts` | `cn()`(clsx+twMerge)、`formatBytes()`、`formatDate()` — Docker 页面统一从此导入 |
| UI | `components/ui/` | shadcn/ui 组件（@base-ui/react 原语），不手动修改 |
| 认证 | `contexts/AuthContext.tsx` | 全局认证状态，初始化时调 `/auth/me` 验证 token |

### Docker 后端目录拆分

重构后，Docker 相关业务按领域拆分到子包/子目录，避免单文件过大：

```
api/docker/
├── __init__.py          # 总路由，prefix=/api/docker，include 各子路由
├── containers.py        # /api/docker/containers/*
├── images.py            # /api/docker/images/*
├── registries.py        # /api/docker/registries/*
├── compose.py           # /api/docker/compose/*
└── host.py              # /api/docker/host/*

models/docker/
├── __init__.py
├── container.py         # DockerContainer、DockerMirrorConfig
└── compose.py           # DockerComposeProject、DockerComposeVersion、DockerComposeStack、COMPOSE_PROJECT_LABEL

schemas/docker/
├── __init__.py
├── container.py
├── image.py
├── registry.py
├── compose.py
└── host.py

services/
├── docker/              # Docker 容器/镜像/宿主机/拉取任务
│   ├── __init__.py
│   ├── container_service.py
│   ├── image_service.py
│   ├── host_service.py
│   ├── pull_task_service.py
│   └── docker_common.py
└── compose/             # Docker Compose 编排与自动发现
    ├── __init__.py
    ├── compose_service.py
    └── compose_discovery.py
```

`app/core/docker_manager.py` 与 `app/core/compose_manager.py` 目前保留为兼容入口，内部重新导出 `services.docker.*` / `services.compose.*` 中的实现，避免外部导入和测试一次性大面积改动。

## 数据模型关系

```
User 1--* AppInstance 1--1 DockerComposeProject
DockerComposeProject 1--* DockerComposeVersion
DockerComposeProject 1--1 DockerComposeStack
```

- `DockerComposeProject` 是独立实体，不依赖插件实例；其当前激活版本通过 `DockerComposeVersion.is_current` 标识。
- Compose 运行时文件写入 `COMPOSE_WORKSPACE_DIR`（默认 `./data/compose`），并自动注入 `nasdeck.compose.project` 标签用于归属识别。

## API 响应格式规范

所有接口（除 204 No Content 外）统一返回 `StandardResponse` 格式：

```json
// 成功
{"success": true, "data": ..., "message": "ok"}

// 错误
{"success": false, "data": null, "message": "错误描述"}
```

- 后端路由层**直接返回数据**，`CustomAPIRoute` 自动包装，无需手动构造 `StandardResponse`
- 业务异常统一使用 `APIException(message, status_code)`，**禁止使用 `HTTPException`**
- 204 No Content（删除操作）保持空响应体，不包装
- 前端 Axios 拦截器自动解包 `data` 字段（要求响应带 `success` 标识），`src/api/` 层函数统一返回解包后的业务数据
- 错误消息通过 `error.displayMessage` 传递给页面层 toast

完整规范见 `docs/api/api-response-spec.md`。

## 异步部署任务机制

部署类操作（应用部署、编排部署/导入、Compose 创建/编辑/启停）均为**异步任务**，不是同步请求：

- 后端：POST 接口立即返回 `task_id`（`DeployTaskCreateResponse`），实际部署由 `services/orchestration/deploy_task_service.py` 在后台执行；进度通过 SSE `GET /api/deploy-tasks/{task_id}/events` 推送（事件内嵌 `_task_status` 标记完成/失败）。
- 前端：`hooks/useDeployTasks.ts` 管理任务状态与 SSE 连接，`components/DeployProgressDialog.tsx` 通过 `DeployTaskContext` 全局监听并展示进度；发起部署的组件调用 `startTask(taskId)` 接入。
- 镜像拉取有独立的任务机制（`pull_task_service` + `useAllPullProgress`），不复用部署任务通道。

## 应用商店图标规则

- 内置/本地应用图标统一放在 `frontend/public/icons/apps/<app-name>.svg`，Vite 构建时会自动复制到 `dist/icons/apps/`。
- 前端统一使用 `frontend/src/pages/apps/AppIcon.tsx` 渲染图标：
  - 仅当 `app.icon` 为 `http/https` 外链时直接使用；
  - 其他情况（本地路径或空）一律回退到 `/icons/apps/${app.name}.svg`。
- 后端**不再提供** `/api/apps/{name}/icon` 图标文件接口；`apps.icon` 字段仅用于外部图标 URL。
- 新增或替换图标时，无需修改数据库，只要按应用名放置/替换 svg 文件即可。

## 应用客户端与认证检测

应用在自动化编排（`orchestrations`）中的认证检测，由各应用专属客户端提供，不要写成独立的认证检测模块。

### 后端

- 应用客户端统一放在 `backend/app/services/apps/`，每个应用一个子包：

  ```text
  services/apps/
  ├── base.py              # AppClient 抽象基类、AuthVerifyResult
  ├── registry.py          # app_name -> client_class 注册表
  └── <app>/
      ├── __init__.py
      └── client.py        # 继承 AppClient，实现 verify_auth，并 register_client
  ```

- `verify_auth(config: dict)` 接收编排实例中保存的认证配置（`url`、`auth_type`、`username`、`password`、`api_key` 等），返回 `AuthVerifyResult(valid, message)`。
- 统一检测入口为 `POST /api/orchestrations/auth/verify`，由 `orchestration_service.verify_app_auth()` 根据 `app_name` 调度对应客户端。
- 新增应用时，只需新增客户端子包并注册，无需修改 API 路由或 Service 调度逻辑。

### 前端

- 通用检测 Hook 为 `useVerifyAppAuth`，接口类型定义在 `frontend/src/api/orchestrations.ts`（hooks 层 re-export）。
- `AutomationImportDialog` 和 `AppConfigPanel` 已内置检测按钮，新增应用无需改动 UI。
- 认证配置是否可检测，统一通过 `frontend/src/pages/automation/auth-config-utils.ts` 中的 `isAuthConfigReady()` 判断。

## 关键约定

- **注释语言**：中文（docstring + `#` 行内注释）
- **Python 环境**：开发环境使用 `backend/.venv/bin/python`（Linux）或 `backend/.venv/Scripts/python.exe`（Windows）；运行命令需设置 `PYTHONPATH=./app`
- **数据库**：PostgreSQL + asyncpg 异步驱动，默认 `DATABASE_URL=postgresql+asyncpg://nasdeck:nasdeck@localhost:5434/nasdeck`（见 `.env`）；测试使用内存 SQLite（`sqlite+aiosqlite:///:memory:`），不影响开发库。
  - **改表结构 / 新增表**：写 Alembic migration，然后执行 `alembic upgrade head`。
  - **修改数据**（如应用商店默认配置、内置应用模板、实例配置）：直接改数据库或写初始化/修复脚本，**不要生成 Alembic migration**。
- **认证**：JWT Bearer token（HS256），**第一个**注册用户自动成为 `admin`，后续注册用户为普通 `user`；token 有效期 24 小时
- **CORS**：开发环境 `allow_origins=["*"]`
- **路径别名**：前端 `@/` 映射到 `src/`
- **Vite 代理**：开发时 `/api` 代理到 `http://localhost:5001`
- **前端请求约定**：组件/hooks **禁止直接 import `@/lib/api` 发请求**，必须在 `src/api/` 对应领域文件中新增/复用封装函数；新增接口时类型与后端 Pydantic schema 保持对齐（含字段可选性）
- **React Query**：hooks 中 mutation 的 `onSuccess` 自动调用 `invalidateQueries` 刷新缓存；容器/Compose 项目列表 10 秒轮询，Stack 状态 30 秒轮询
- **Docker 管理**：可选功能，后端通过 `docker_manager.available` 检测可用性，不可用时安全降级
- **Compose 管理**：通过 `docker compose` CLI 操作；`compose_service` 维护项目级异步锁防止并发操作冲突
- **Toast 通知**：前端使用自定义 `ToastProvider`（`components/ui/toast.tsx`），通过 `useToast()` 调用
- **页面拆分**：复杂页面按功能拆分为子组件，放在同目录下；Docker 跨页面共享组件在 `docker/shared/`
- **业务下沉**：新增业务逻辑优先放到 `services/` 对应领域文件，避免再向 `core/docker_manager.py`、`core/compose_manager.py` 兼容入口追加代码
