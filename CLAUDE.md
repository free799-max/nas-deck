# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

NasDeck — 内容订阅聚合平台，追踪多种内容源（Jellyfin/Komga/MoviePilot）的更新，通过 Telegram/钉钉/企业微信推送通知。单体微内核插件化架构。

## 开发命令

### 后端（`backend/` 目录下）

```bash
# 使用虚拟环境中的 Python（系统 python 指向 Windows Store 占位程序）
backend/.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 运行全部测试
backend/.venv/Scripts/python.exe -m pytest

# 运行单个测试文件
backend/.venv/Scripts/python.exe -m pytest tests/test_auth.py

# 运行单个测试函数
backend/.venv/Scripts/python.exe -m pytest tests/test_auth.py::test_register -v

# 数据库迁移
backend/.venv/Scripts/python.exe -m alembic upgrade head
```

### 前端（`frontend/` 目录下）

```bash
npm run dev          # 开发服务器（Vite，代理 /api -> localhost:8000）
npm run build        # TypeScript 编译 + Vite 构建
npm run lint         # ESLint 检查
```

### Docker

```bash
docker-compose up --build   # 构建并启动前后端容器（后端 :8000，前端 :3000）
```

## 架构

### 请求生命周期

```
用户请求 -> Nginx(生产) / Vite Proxy(开发) -> FastAPI -> SQLAlchemy(异步) -> SQLite
                                              |
                                              +-> JWT 认证(get_current_user 依赖注入)
                                              +-> 插件系统(BasePlugin 子类)
                                              +-> 通知引擎(BaseNotifier 子类)
```

### 后端分层（`backend/app/`）

| 层 | 目录 | 职责 |
|---|---|---|
| 入口 | `main.py` | FastAPI 实例、lifespan（启动时初始化DB/发现插件/启动调度器）、CORS、路由注册、通知渠道注册 |
| 配置 | `config.py` | pydantic-settings，从 `.env` 或环境变量加载（APP_NAME/DATABASE_URL/SECRET_KEY/ACCESS_TOKEN_EXPIRE_MINUTES/PLUGIN_DIR） |
| 数据库 | `database.py` | SQLAlchemy 2.0 异步引擎(aiosqlite)、会话工厂、`get_db()` 依赖（自动 commit/rollback） |
| API | `api/` | 5 个路由模块，均需 JWT 认证（auth/plugins/subscriptions/notifications/docker） |
| 核心 | `core/` | security(JWT+bcrypt)、scheduler(30分钟轮询)、plugin_loader(自动发现)、docker_manager、notification_engine |
| 通知器 | `core/notifiers/` | BaseNotifier 抽象基类 + Telegram/DingTalk/WeChatWork 实现 |
| 模型 | `models/` | 6 个 SQLAlchemy ORM 模型（User/PluginInstance/Subscription/UpdateLog/NotificationChannel/DockerContainer） |
| Schema | `schemas/` | Pydantic 请求/响应模型，与 API 端点一一对应 |
| 插件 | `plugins/` | BasePlugin 抽象基类 + 3 个实现（jellyfin/komga/moviepilot） |

### 前端分层（`frontend/src/`）

| 层 | 目录 | 职责 |
|---|---|---|
| 入口 | `App.tsx` | QueryClientProvider + BrowserRouter + ProtectedRoute(鉴权守卫，检查 localStorage token) |
| 布局 | `layouts/` | AppLayout(Sidebar+TopBar+Outlet)、Sidebar(7个导航项)、TopBar |
| 页面 | `pages/` | 7 个页面组件，对应路由 |
| 数据 | `hooks/` | React Query hooks，接口类型定义在此（非独立 types 目录） |
| API | `lib/api.ts` | Axios 实例，请求拦截器附加 Bearer token，401 时跳转 /login |
| UI | `components/ui/` | shadcn/ui 组件（@base-ui/react 原语），不手动修改 |

### 插件系统

插件通过 `pkgutil.iter_modules` 自动发现 `app/plugins/` 包下的子模块。每个插件继承 `BasePlugin`，实现 4 个抽象方法：

- `test_connection(config) -> bool` — 测试连接
- `get_sources(config) -> list[Source]` — 获取数据源列表
- `get_items(config, source_id) -> list[Item]` — 获取数据项
- `check_updates(config, subscriptions) -> list[Update]` — 检查更新

插件的 `config_schema` 是 JSON Schema，前端据此动态渲染配置表单。

### 定时调度

`APScheduler` 每 30 分钟执行 `SubscriptionChecker.run()`，流程：
1. 查询所有已启用的 `PluginInstance`
2. 获取每个实例关联的活跃 `Subscription`
3. 调用 `plugin.check_updates()` 检测更新
4. 写入 `UpdateLog` 记录
5. 通过 `NotificationEngine` 向所有已启用渠道推送

## 数据模型关系

```
User 1--* Subscription *--1 PluginInstance 1--1 DockerContainer
User 1--* NotificationChannel
Subscription 1--* UpdateLog（级联删除）
```

## 关键约定

- **注释语言**：中文（docstring + `#` 行内注释）
- **Python 环境**：必须使用 `backend/.venv/Scripts/python.exe`，系统 `python` 是 Windows Store 占位程序
- **数据库**：SQLite + aiosqlite 异步驱动，开发时数据库文件在 `backend/nasdeck.db`
- **认证**：JWT Bearer token，`register` 端点默认赋予 `admin` 角色
- **CORS**：开发环境 `allow_origins=["*"]`
- **路径别名**：前端 `@/` 映射到 `src/`
- **Vite 代理**：开发时 `/api` 代理到 `http://localhost:8000`
- **React Query**：hooks 中 mutation 的 `onSuccess` 自动调用 `invalidateQueries` 刷新缓存
- **Docker 管理**：可选功能，后端通过 `docker_manager.available` 检测可用性，不可用时安全降级
