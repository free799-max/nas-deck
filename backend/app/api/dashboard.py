"""服务概览 API 路由。"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.custom_route import CustomAPIRoute
from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.dashboard import OverviewAppDetailOut, OverviewOut
from app.services.overview import overview_service

router = APIRouter(
    prefix="/api/dashboard",
    tags=["dashboard"],
    route_class=CustomAPIRoute,
)


@router.get("/overview", response_model=OverviewOut)
async def get_overview(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回按分类聚合的已部署应用与自动生成的访问地址。"""
    # 使用浏览器实际访问的主机名生成跳转链接，避免容器内网 IP 不可达
    host = request.headers.get("x-forwarded-host") or request.url.netloc
    return await overview_service.get_overview(db, host=host)


@router.get("/apps/{instance_id}", response_model=OverviewAppDetailOut)
async def get_app_detail(
    instance_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回单个应用的容器基本信息与实时监控指标。"""
    host = request.headers.get("x-forwarded-host") or request.url.netloc
    return await overview_service.get_app_detail(
        db, instance_id=instance_id, host=host
    )
