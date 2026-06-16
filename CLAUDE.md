# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

NasDeck — NAS 管理平台，提供 Docker 容器/镜像/Compose Stack 管理、插件系统（Jellyfin/Komga/MoviePilot）和看板视图。单体微内核插件化架构，前后端分离。

## 开发命令

### 后端（在项目根目录执行）

```bash
# 启动开发服务器
PYTHONPATH=./app .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 5001

# 运行全部测试（需在 backend 目录下执行，否则 pytest 找不到测试文件）
cd backend
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
用户请求 -> Nginx(生产) / Vite Proxy(开发) -> FastAPI -> SQLAlchemy(异步) -> SQLite
                                              |
                                              +-> JWT 认证(get_current_user 依赖注入)
                                              +-> CustomAPIRoute 自动包装 StandardResponse
                                              +-> 插件系统(BasePlugin 子类)
                                              +-> services/ 业务层 -> Docker SDK / docker compose CLI
```

### 后端分层（`backend/app/`）

| 层 | 目录 | 职责 |
|---|---|---|
| 入口 | `main.py` | FastAPI 实例、lifespan（初始化DB/发现插件）、CORS、路由注册、全局异常处理器 |
| 配置 | `config.py` | pydantic-settings，从 `.env` 加载（APP_NAME/DATABASE_URL/SECRET_KEY/ACCESS_TOKEN_EXPIRE_MINUTES/PLUGIN_DIR/COMPOSE_WORKSPACE_DIR） |
| 数据库 | `database.py` | SQLAlchemy 2.0 异步引擎(aiosqlite)、会话工厂、`get_db()` 依赖（自动 commit/rollback） |
| API | `api/` | 路由模块（auth/plugins/docker），Docker 路由已按领域拆分为 `api/docker/` 子包 |
| 核心 | `core/` | 基础设施：security(JWT+bcrypt)、plugin_loader(自动发现)、custom_route(响应包装)、exceptions。`docker_manager.py` 与 `compose_manager.py` 目前仅作为兼容入口保留 |
| 业务服务 | `services/` | 按功能域拆分为 `services/docker/`（容器/镜像/宿主机/拉取任务）和 `services/compose/`（Compose 编排/自动发现） |
| 初始化 | `initializers/` | 应用启动时的业务初始化，如默认 Docker Hub 镜像仓库配置 |
| 模型 | `models/` | SQLAlchemy ORM 模型；Docker 相关模型按领域拆分为 `models/docker/` 子包 |
| Schema | `schemas/` | Pydantic 请求/响应模型；Docker 相关 Schema 按领域拆分为 `schemas/docker/` 子包 |
| 插件 | `plugins/` | BasePlugin 抽象基类 + 3 个实现（jellyfin/komga/moviepilot） |

### 前端分层（`frontend/src/`）

| 层 | 目录 | 职责 |
|---|---|---|
| 入口 | `App.tsx` | QueryClientProvider + AuthProvider + ToastProvider + BrowserRouter + ProtectedRoute |
| 布局 | `layouts/` | AppLayout(Sidebar+TopBar+Outlet)、Sidebar(导航)、TopBar |
| 页面 | `pages/` | 按功能域组织子目录：`auth/`、`dashboard/`(含 components/)、`services/`、`docker/`(含 containers/images/stacks/host/shared) |
| 数据 | `hooks/` | React Query hooks，接口类型定义在此（非独立 types 目录）。容器/镜像/Stack 列表 30 秒自动刷新 |
| API | `lib/api.ts` | Axios 实例，请求拦截器附加 Bearer token，响应拦截器解包 StandardResponse，401 时跳转 /login |
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

### 插件系统

插件通过 `pkgutil.iter_modules` 自动发现 `app/plugins/` 包下的子模块。每个插件继承 `BasePlugin`，实现 3 个抽象方法：

- `test_connection(config) -> bool` — 测试连接
- `get_sources(config) -> list[Source]` — 获取数据源列表
- `get_items(config, source_id) -> list[Item]` — 获取数据项

插件的 `config_schema` 是 JSON Schema，前端据此动态渲染配置表单。

## 数据模型关系

```
User 1--* PluginInstance 1--1 DockerContainer
PluginInstance  <-- DockerMirrorConfig（独立配置表）
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
- 前端 Axios 拦截器自动解包 `data` 字段，hooks 中直接使用 `response.data`
- 错误消息通过 `error.displayMessage` 传递给页面层 toast

完整规范见 `docs/api/api-response-spec.md`。

## 关键约定

- **注释语言**：中文（docstring + `#` 行内注释）
- **Python 环境**：开发环境使用 `backend/.venv/bin/python`（Linux）或 `backend/.venv/Scripts/python.exe`（Windows）；运行命令需设置 `PYTHONPATH=./app`
- **数据库**：SQLite + aiosqlite 异步驱动，开发时数据库文件在 `backend/nasdeck.db`；容器化部署时通过 `.env` 指向 `./data/nasdeck.db`
- **认证**：JWT Bearer token（HS256），`register` 端点默认赋予 `admin` 角色，token 有效期 24 小时
- **CORS**：开发环境 `allow_origins=["*"]`
- **路径别名**：前端 `@/` 映射到 `src/`
- **Vite 代理**：开发时 `/api` 代理到 `http://localhost:5001`
- **React Query**：hooks 中 mutation 的 `onSuccess` 自动调用 `invalidateQueries` 刷新缓存
- **Docker 管理**：可选功能，后端通过 `docker_manager.available` 检测可用性，不可用时安全降级
- **Compose 管理**：通过 `docker compose` CLI 操作；`compose_service` 维护项目级异步锁防止并发操作冲突
- **Toast 通知**：前端使用自定义 `ToastProvider`（`components/ui/toast.tsx`），通过 `useToast()` 调用
- **页面拆分**：复杂页面按功能拆分为子组件，放在同目录下；Docker 跨页面共享组件在 `docker/shared/`
- **业务下沉**：新增业务逻辑优先放到 `services/` 对应领域文件，避免再向 `core/docker_manager.py`、`core/compose_manager.py` 兼容入口追加代码
