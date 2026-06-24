"""系统设置 API 模块。

提供系统全局配置的查询、更新以及目录浏览/操作接口。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.custom_route import CustomAPIRoute
from app.core.exceptions import APIException
from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.system_config import SystemConfigOut, SystemConfigUpdate
from app.schemas.docker import (
    DirectoryCreateRequest,
    DirectoryDeleteRequest,
    DirectoryEntry,
    DirectoryList,
    DirectoryRenameRequest,
)
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


async def _get_host_root_dir(db: AsyncSession) -> str:
    """获取宿主机根目录，未配置时抛异常。"""
    config = await system_config_service.get_or_create(db)
    if not config.storage_host_root_dir:
        raise APIException("未配置宿主机根目录", 400)
    return config.storage_host_root_dir


@router.get("/directories", response_model=DirectoryList)
async def list_directories(
    path: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出宿主机指定路径下的目录列表。

    用于前端目录选择器浏览文件系统，与 Docker 无关。
    只能浏览已配置的宿主机根目录及其子目录。
    目标路径不存在时返回空列表，避免前端目录选择器因自动生成的父路径报错。
    """
    root_path = await _get_host_root_dir(db)
    try:
        return filesystem_service.list_directories(path, root_path=root_path)
    except APIException as exc:
        if exc.status_code == 404 and "路径不存在" in exc.message:
            return {"path": path, "entries": [], "exists": False}
        raise


@router.post("/directories", response_model=DirectoryEntry)
async def create_directory(
    data: DirectoryCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """在指定父目录下创建子目录。"""
    root_path = await _get_host_root_dir(db)
    target_path = f"{data.path.rstrip('/')}/{data.name}"
    return filesystem_service.create_directory(target_path, root_path=root_path)


@router.put("/directories", response_model=DirectoryEntry)
async def rename_directory(
    data: DirectoryRenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重命名目录。"""
    root_path = await _get_host_root_dir(db)
    return filesystem_service.rename_directory(
        data.old_path,
        data.new_name,
        root_path=root_path,
    )


@router.delete("/directories")
async def delete_directory(
    data: DirectoryDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除目录（递归删除非空目录）。"""
    root_path = await _get_host_root_dir(db)
    filesystem_service.delete_directory(data.path, root_path=root_path)
    return {"success": True}
