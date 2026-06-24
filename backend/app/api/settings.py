"""系统设置 API 模块。

提供系统全局配置的查询、更新以及目录浏览接口。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.custom_route import CustomAPIRoute
from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.system_config import SystemConfigOut, SystemConfigUpdate
from app.schemas.docker import DirectoryList
from app.services.host.filesystem_service import filesystem_service
from app.services.system_config_service import system_config_service

router = APIRouter(prefix="/api/settings", tags=["settings"], route_class=CustomAPIRoute)


@router.get("", response_model=SystemConfigOut)
async def get_system_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取系统全局配置。

    首次调用时若数据库中无记录，会自动创建默认配置。
    """
    config = await system_config_service.get_or_create(db)
    return system_config_service.to_dict(config)


@router.put("", response_model=SystemConfigOut)
async def update_system_config(
    data: SystemConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新系统全局配置。"""
    config = await system_config_service.update(db, data)
    return system_config_service.to_dict(config)


@router.get("/directories", response_model=DirectoryList)
async def list_directories(
    path: str,
    current_user: User = Depends(get_current_user),
):
    """列出宿主机指定路径下的目录列表。

    用于前端目录选择器浏览文件系统，与 Docker 无关。
    """
    return filesystem_service.list_directories(path)
