# EverySub 设计文档

## 概述

EverySub 是一个内容订阅聚合平台，追踪电影、短剧、漫画、小说、新闻等各类内容源的更新，并通过多渠道推送通知。采用微内核插件化架构，通过 Docker Sidecar 模式对接和管理各类开源项目。

## 技术栈

- 后端：Python + FastAPI + SQLAlchemy + Alembic + APScheduler
- 前端：React + Vite + TypeScript + Tailwind CSS + shadcn/ui + TanStack Query
- 数据库：SQLite（默认）/ PostgreSQL（可选）
- 容器：Docker + docker-py + Docker Compose
- 认证：JWT
- 部署：Docker 容器化

## 架构：单体微内核

插件以 Python 模块形式加载到 FastAPI 进程内，每个插件实现统一接口。

```
EverySub (FastAPI)
├── 核心：用户/订阅/通知/调度
├── 插件加载器（importlib 动态加载）
├── 插件：JellyfinPlugin / KomgaPlugin / MoviePilotPlugin
├── Docker 管理模块（docker-py）
├── 通知引擎（Telegram / 钉钉 / 企业微信）
└── 定时调度（APScheduler）
```

## 插件系统

### 插件基类接口

```python
class BasePlugin(ABC):
    name: str              # "jellyfin"
    display_name: str      # "Jellyfin"
    version: str           # "1.0.0"
    description: str
    config_schema: dict    # JSON Schema，前端动态渲染配置表单

    async def test_connection(self, config: dict) -> bool
    async def get_sources(self, config: dict) -> list[Source]
    async def get_items(self, config: dict, source_id: str) -> list[Item]
    async def check_updates(self, config: dict, subscriptions: list) -> list[Update]
```

### 插件加载机制

- 插件放在 `backend/plugins/` 目录下，每个插件一个子目录
- 启动时通过 `importlib` 扫描并加载所有继承 BasePlugin 的类
- 插件通过 config_schema 声明配置项，前端根据 schema 动态渲染表单

### 两层订阅模型

1. 添加插件实例（全局，如 "我的Jellyfin", url=..., api_key=...）
2. 从插件实例中浏览可订阅内容（get_sources → get_items）
3. 用户选择具体内容订阅
4. Scheduler 定时调用 check_updates 检查更新
5. 有更新 → 触发通知

### MVP 内置插件

- jellyfin — 对接 Jellyfin API，追踪媒体库新增内容
- komga — 对接 Komga API，追踪漫画/书籍更新
- moviepilot — 对接 MoviePilot API，追踪下载/订阅状态

## 数据模型

### 核心实体

- **User** — id, username, password, role, created_at
- **PluginInstance**（全局） — id, plugin_name, display_name, config(JSON), docker_id, enabled, created_at
- **Subscription** — id, user_id(FK), instance_id(FK), item_id, item_title, item_meta(JSON), last_checked, status, created_at
- **UpdateLog** — id, subscription_id(FK), title, content, detected_at, notified
- **NotificationChannel** — id, user_id(FK), type(tg/dd/wx), config(JSON), enabled, created_at
- **DockerContainer** — id, instance_id(FK), container_id, name, status, health, last_checked

### 关系

- PluginInstance 是全局资源，管理员配置，不关联用户
- User → 多个 Subscription（用户订阅了哪些内容）
- Subscription → 多个 UpdateLog（更新历史）
- PluginInstance → DockerContainer（关联管理的容器，可为空）
- User → 多个 NotificationChannel（通知渠道配置）

## Docker 管理

### 两种管理模式

1. **Docker API 模式 (docker-py)** — 直接操作容器：启动/停止/重启/删除，实时状态和健康检查
2. **Docker Compose 模式** — 管理 compose 文件，通过 subprocess 调用 docker compose

### 与插件的关系

- 添加 PluginInstance 时可选择"由 EverySub 管理容器"或"仅对接已有服务"
- 管理模式下 EverySub 负责拉起/监控容器
- Scheduler 定时检查容器状态，状态变化时触发通知

## 通知系统

### 通知渠道接口

```python
class BaseNotifier(ABC):
    name: str
    config_schema: dict

    async def send(self, title: str, content: str, **kwargs) -> bool
    async def test(self, config: dict) -> bool
```

### 触发源

- 内容更新（check_updates 发现新内容）
- 容器状态变化（stopped / unhealthy）

### 通知策略

- 即时通知：状态异常立即推送
- 聚合通知：内容更新按周期汇总推送
- 静默时段：可配置免打扰时间段

### 内置渠道

- TelegramNotifier — Bot API
- DingTalkNotifier — Webhook
- WeChatWorkNotifier — Webhook

## 前端设计

### UI 风格（参考图）

- 左侧固定侧边栏 + 顶部搜索栏
- 看板式卡片布局，柔和渐变色背景（淡紫/淡粉/淡蓝/淡绿）
- 白底、圆角卡片 (rounded-xl)、轻阴影
- 彩色 badge 区分内容类型
- 深色模式支持

### 页面结构

| 页面 | 内容 |
|------|------|
| Dashboard | 看板概览，按状态分列（有更新/正常/异常） |
| 订阅管理 | 按插件实例分组，订阅列表，搜索/筛选 |
| Docker 管理 | 容器列表，状态指示灯，启停操作 |
| 通知中心 | 通知历史时间线，按类型筛选 |
| 插件管理 | 已安装插件 + 添加插件实例（动态表单） |
| 通知渠道 | 配置通知渠道，测试发送 |
| 用户管理 | 用户 CRUD，角色分配 |

### 侧边栏导航

- Dashboard
- 订阅管理
- Docker 管理
- 通知中心
- 插件管理
- 通知渠道
- 用户管理

## 项目目录结构

```
every-sub-1/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── plugins.py
│   │   │   ├── subscriptions.py
│   │   │   ├── docker.py
│   │   │   └── notifications.py
│   │   ├── core/
│   │   │   ├── plugin_loader.py
│   │   │   ├── scheduler.py
│   │   │   ├── docker_manager.py
│   │   │   └── notification_engine.py
│   │   └── plugins/
│   │       ├── base.py
│   │       ├── jellyfin/
│   │       ├── komga/
│   │       └── moviepilot/
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── layouts/
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── App.tsx
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```
