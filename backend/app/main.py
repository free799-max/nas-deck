"""NasDeck 应用入口模块。

负责创建 FastAPI 应用实例、注册中间件和路由、
管理应用生命周期（数据库初始化、插件发现、定时调度）。
"""

from contextlib import asynccontextmanager

import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.exceptions import APIException
from app.schemas.response import StandardResponse
from app.core.custom_route import CustomAPIRoute

from app.config import settings
from app.api.auth import router as auth_router
from app.api.orchestrations import router as orchestrations_router
from app.api.app_store import router as apps_router
from app.api.orchestration.deploy_tasks import router as deploy_tasks_router
from app.api.settings import router as settings_router
# trigger-reload: docker_manager fixed

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化资源，关闭时释放资源。"""
    # 执行数据库迁移（包含 schema 与内置数据初始化）
    import asyncio
    from pathlib import Path
    from alembic.config import Config
    from alembic import command

    backend_dir = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    # alembic env 内部使用 asyncio.run，必须在独立线程执行以避免与当前事件循环冲突
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")

    yield


# 创建 FastAPI 应用实例
app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.router.route_class = CustomAPIRoute


@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    """捕获业务 API 异常，返回统一格式。"""
    return JSONResponse(
        status_code=exc.status_code,
        content=StandardResponse.fail(exc.message).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """捕获 FastAPI HTTPException，统一包装为标准格式。"""
    message = exc.detail if isinstance(exc.detail, str) else "请求失败"
    return JSONResponse(
        status_code=exc.status_code,
        content=StandardResponse.fail(message).model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """捕获未预料异常，返回 500 统一格式。"""
    logger.exception("未处理异常: %s", exc)
    return JSONResponse(
        status_code=500,
        content=StandardResponse.fail("服务器内部错误").model_dump(),
    )

# 配置 CORS 中间件，允许所有来源（开发环境）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册所有 API 路由
app.include_router(auth_router)
app.include_router(orchestrations_router)
app.include_router(apps_router)
app.include_router(deploy_tasks_router, prefix="/api")
app.include_router(settings_router)

# Docker 管理路由（依赖可选的 Docker 环境）
from app.api.docker import router as docker_router
app.include_router(docker_router)


@app.get("/api/health")
async def health_check():
    """健康检查端点，用于监控应用运行状态。"""
    return {"status": "ok", "app": settings.APP_NAME}
