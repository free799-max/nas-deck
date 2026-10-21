"""系统设置 API 模块。

提供系统全局配置的查询、更新、数据目录管理以及目录浏览/操作接口。
"""

import asyncio

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.custom_route import CustomAPIRoute
from app.core.exceptions import APIException
from app.core.security import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.system_config import SystemConfigOut, SystemConfigUpdate
from app.schemas.storage_directory import (
    StorageDirectoryCreate,
    StorageDirectoryOut,
    StorageDirectoryUpdate,
)
from app.schemas.docker import (
    DirectoryCreateRequest,
    DirectoryDeleteRequest,
    DirectoryEntry,
    DirectoryList,
    DirectoryRenameRequest,
)
from app.services.host.filesystem_service import filesystem_service
from app.services.system.port_allocator import allocate_free_ports, get_used_ports
from app.services.system import (
    get_browse_roots,
    storage_directory_service,
    system_config_service,
)

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
    current_user: User = Depends(require_admin),
):
    """更新系统全局配置。"""
    config = await system_config_service.update(db, data)
    return system_config_service.to_dict(config)


@router.get("/port-suggestions")
async def get_port_suggestions(
    count: int = Query(..., ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取服务端口分配建议。

    从系统设置的 service_port_start 开始顺序挑选 count 个空闲端口，
    供部署表单初始化时预填，与部署时的顺序分配结果保持一致。
    """
    config = await system_config_service.get_or_create(db)
    start = config.service_port_start or 10000
    used = await asyncio.to_thread(get_used_ports)
    try:
        ports = allocate_free_ports(used, count, start)
    except ValueError as e:
        raise APIException(str(e), 400) from e
    return {"ports": ports}


@router.get("/directories", response_model=DirectoryList)
async def list_directories(
    path: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出宿主机指定路径下的目录列表。

    用于前端目录选择器浏览文件系统，与 Docker 无关。
    只能浏览可见存储目录（含应用数据目录）及其子目录。
    目标路径不存在时返回空列表，避免前端目录选择器因自动生成的父路径报错。
    """
    root_paths = await get_browse_roots(db)
    try:
        return filesystem_service.list_directories(path, root_paths=root_paths)
    except APIException as exc:
        if exc.status_code == 404 and "路径不存在" in exc.message:
            return {"path": path, "entries": [], "exists": False}
        raise


@router.post("/directories", response_model=DirectoryEntry)
async def create_directory(
    data: DirectoryCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """在指定父目录下创建子目录。"""
    root_paths = await get_browse_roots(db)
    target_path = f"{data.path.rstrip('/')}/{data.name}"
    return filesystem_service.create_directory(target_path, root_paths=root_paths)


@router.put("/directories", response_model=DirectoryEntry)
async def rename_directory(
    data: DirectoryRenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """重命名目录。"""
    root_paths = await get_browse_roots(db)
    return filesystem_service.rename_directory(
        data.old_path,
        data.new_name,
        root_paths=root_paths,
    )


@router.delete("/directories")
async def delete_directory(
    data: DirectoryDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """删除目录（递归删除非空目录）。"""
    root_paths = await get_browse_roots(db)
    filesystem_service.delete_directory(data.path, root_paths=root_paths)
    return {"success": True}


# ---------- 数据目录管理 ----------


@router.get("/storage-directories", response_model=list[StorageDirectoryOut])
async def list_storage_directories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出全部数据目录（按 sort_order、id 排序），附带容器可见性。"""
    directories = await storage_directory_service.list(db)
    return [storage_directory_service.to_dict(d) for d in directories]


@router.post("/storage-directories", response_model=StorageDirectoryOut)
async def create_storage_directory(
    data: StorageDirectoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """创建数据目录。"""
    directory = await storage_directory_service.create(db, data)
    return storage_directory_service.to_dict(directory)


@router.put("/storage-directories/{dir_id}", response_model=StorageDirectoryOut)
async def update_storage_directory(
    dir_id: int,
    data: StorageDirectoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """更新数据目录，不存在时返回 404。"""
    directory = await storage_directory_service.update(db, dir_id, data)
    return storage_directory_service.to_dict(directory)


@router.delete("/storage-directories/{dir_id}")
async def delete_storage_directory(
    dir_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """删除数据目录，不存在时返回 404。"""
    await storage_directory_service.delete(db, dir_id)
    return {"success": True}
