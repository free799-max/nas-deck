# NasDeck

内容订阅聚合平台，追踪 Jellyfin、Komga、MoviePilot 等内容源的更新，通过 Telegram、钉钉、企业微信推送通知。

## 功能特性

- **多源订阅**：支持 Jellyfin（影视）、Komga（漫画）、MoviePilot（自动化）等内容源
- **自动更新检测**：每 30 分钟轮询检查订阅内容更新
- **多渠道通知**：支持 Telegram、钉钉、企业微信推送
- **Docker 管理**：集成 Docker 容器管理（可选，无 Docker 环境时自动降级）
- **插件化架构**：基于 `BasePlugin` 抽象基类，新内容源可通过插件扩展
- **统一 API 响应**：所有接口返回标准格式 `{success, data, message}`

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12 + FastAPI + SQLAlchemy 2.0 (异步) + SQLite |
| 前端 | React 19 + TypeScript + Tailwind CSS + shadcn/ui |
| 数据 | SQLite + aiosqlite (异步驱动) |
| 调度 | APScheduler (30 分钟轮询) |
| 认证 | JWT Bearer Token + bcrypt |
| 容器 | Docker + docker-compose |

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 20+
- Docker（可选，用于容器管理功能）

### 1. 克隆仓库

```bash
git clone https://github.com/free799-max/nas-deck.git
cd nas-deck
```

### 2. 后端启动

```bash
cd backend

# 创建虚拟环境（Windows）
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 启动服务
PYTHONPATH=./app .venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端默认运行在 `http://localhost:8000`，API 文档见 `http://localhost:8000/docs`。

### 3. 前端启动

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`，开发时代理 `/api` 到 `localhost:8000`。

### 4. Docker 一键启动

```bash
docker-compose up --build
```

- 后端：`http://localhost:8000`
- 前端：`http://localhost:3000`

## 开发命令

### 后端

```bash
# 运行全部测试
PYTHONPATH=./app .venv\Scripts\python.exe -m pytest

# 运行单个测试文件
PYTHONPATH=./app .venv\Scripts\python.exe -m pytest tests/test_auth.py

# 数据库迁移
PYTHONPATH=./app .venv\Scripts\python.exe -m alembic upgrade head
```

### 前端

```bash
npm run build   # TypeScript 编译 + Vite 构建
npm run lint    # ESLint 检查
```

## 项目结构

```
nas-deck/
├── backend/
│   ├── app/
│   │   ├── api/              # 路由层（auth/plugins/subscriptions/notifications/docker）
│   │   ├── core/             # 核心逻辑（认证、调度、插件加载、Docker管理、通知引擎）
│   │   ├── models/           # SQLAlchemy ORM 模型
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   ├── plugins/          # 插件实现（jellyfin/komga/moviepilot）
│   │   └── main.py           # FastAPI 入口
│   └── tests/                # 测试套件
├── frontend/
│   └── src/
│       ├── pages/            # 页面组件
│       ├── hooks/            # React Query hooks
│       ├── layouts/          # 布局组件
│       └── lib/api.ts        # Axios 封装
├── docs/
│   └── api/
│       └── api-response-spec.md    # API 响应格式规范
└── docker-compose.yml
```

## 插件开发

继承 `BasePlugin` 并实现 4 个抽象方法即可添加新内容源：

```python
from app.plugins.base import BasePlugin

class MyPlugin(BasePlugin):
    name = "my_plugin"
    display_name = "My Plugin"
    version = "1.0.0"
    config_schema = {...}  # JSON Schema，前端据此渲染配置表单

    async def test_connection(self, config) -> bool: ...
    async def get_sources(self, config) -> list[Source]: ...
    async def get_items(self, config, source_id) -> list[Item]: ...
    async def check_updates(self, config, subscriptions) -> list[Update]: ...
```

将插件文件放入 `backend/app/plugins/` 目录，服务启动时自动发现加载。

## 配置

通过环境变量或 `backend/.env` 文件配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_NAME` | NasDeck | 应用名称 |
| `DATABASE_URL` | sqlite+aiosqlite:///./nasdeck.db | 数据库连接 |
| `SECRET_KEY` | change-me-in-production | JWT 签名密钥 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 1440 | Token 过期时间（分钟）|
| `PLUGIN_DIR` | app/plugins | 插件目录 |

## 数据模型

```
User 1--* Subscription *--1 PluginInstance 1--1 DockerContainer
User 1--* NotificationChannel
Subscription 1--* UpdateLog（级联删除）
```

## API 规范

所有接口（除 204 No Content 外）统一返回标准格式：

```json
{"success": true, "data": ..., "message": "ok"}
{"success": false, "data": null, "message": "错误描述"}
```

完整规范见 [docs/api/api-response-spec.md](docs/api/api-response-spec.md)。
