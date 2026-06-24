"""Docker 宿主机信息相关 API。"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.custom_route import CustomAPIRoute
from app.core.exceptions import APIException
from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.docker import (
    DirectoryCreateRequest,
    DirectoryDeleteRequest,
    DirectoryEntry,
    DirectoryList,
    DirectoryRenameRequest,
    HostInfo,
)
from app.core.docker_manager import docker_manager
from app.services.system_config_service import system_config_service

router = APIRouter(route_class=CustomAPIRoute)


async def _get_host_root_dir(db: AsyncSession) -> str:
    """获取宿主机根目录，未配置时抛异常。"""
    config = await system_config_service.get_or_create(db)
    if not config.storage_host_root_dir:
        raise APIException("未配置宿主机根目录", 400)
    return config.storage_host_root_dir


@router.get("/host/directories", response_model=DirectoryList)
async def list_host_directories(
    path: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出宿主机指定路径下的目录列表。

    仅返回子目录，用于前端目录选择器浏览文件系统。
    只能浏览已配置的宿主机根目录及其子目录。
    目标路径不存在时返回空列表，避免前端目录选择器因自动生成的父路径报错。
    """
    root_path = await _get_host_root_dir(db)
    try:
        return docker_manager.list_directories(path, root_path=root_path)
    except APIException as exc:
        if exc.status_code == 404 and "路径不存在" in exc.message:
            return {"path": path, "entries": [], "exists": False}
        raise


@router.post("/host/directories", response_model=DirectoryEntry)
async def create_host_directory(
    data: DirectoryCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """在指定父目录下创建子目录。"""
    root_path = await _get_host_root_dir(db)
    target_path = f"{data.path.rstrip('/')}/{data.name}"
    return docker_manager.create_directory(target_path, root_path=root_path)


@router.put("/host/directories", response_model=DirectoryEntry)
async def rename_host_directory(
    data: DirectoryRenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重命名目录。"""
    root_path = await _get_host_root_dir(db)
    return docker_manager.rename_directory(
        data.old_path,
        data.new_name,
        root_path=root_path,
    )


@router.delete("/host/directories")
async def delete_host_directory(
    data: DirectoryDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除目录（递归删除非空目录）。"""
    root_path = await _get_host_root_dir(db)
    docker_manager.delete_directory(data.path, root_path=root_path)
    return {"success": True}


@router.get("/host/info", response_model=HostInfo)
async def get_host_info(current_user: User = Depends(get_current_user)):
    """获取 Docker 宿主机综合信息。"""
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    info = docker_manager.get_host_info()
    if not info:
        raise APIException("Docker 不可用", 503)
    return info
