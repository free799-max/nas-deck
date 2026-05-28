"""NasDeck 应用入口模块。

负责创建 FastAPI 应用实例、注册中间件和路由、
管理应用生命周期（数据库初始化、插件发现、定时调度）。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.core.scheduler import setup_scheduler, scheduler
from app.api.auth import router as auth_router
from app.api.plugins import router as plugins_router
from app.api.subscriptions import router as subscriptions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化资源，关闭时释放资源。"""
    # 初始化数据库表结构
    await init_db()

    # 自动发现并加载插件
    from app.core.plugin_loader import plugin_loader
    plugin_loader.discover()

    # 启动定时调度器（订阅更新检查）
    setup_scheduler()

    yield

    # 关闭时停止调度器
    if scheduler.running:
        scheduler.shutdown()


# 创建 FastAPI 应用实例
app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# 配置 CORS 中间件，允许所有来源（开发环境）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 导入通知相关模块
from app.api.notifications import router as notifications_router
from app.core.notification_engine import notification_engine
from app.core.notifiers.telegram import TelegramNotifier
from app.core.notifiers.dingtalk import DingTalkNotifier
from app.core.notifiers.wechat_work import WeChatWorkNotifier

# 注册所有 API 路由
app.include_router(auth_router)
app.include_router(plugins_router)
app.include_router(subscriptions_router)
app.include_router(notifications_router)

# 注册通知渠道实现
notification_engine.register(TelegramNotifier)
notification_engine.register(DingTalkNotifier)
notification_engine.register(WeChatWorkNotifier)

# Docker 管理路由（依赖可选的 Docker 环境）
from app.api.docker import router as docker_router
app.include_router(docker_router)


@app.get("/api/health")
async def health_check():
    """健康检查端点，用于监控应用运行状态。"""
    return {"status": "ok", "app": settings.APP_NAME}
