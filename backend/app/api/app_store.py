"""应用商店 API 路由模块。"""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import APIException
from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.app_store import (
    AppDeployRequest,
    AppDeployResponse,
    AppDetailOut,
    AppOut,
    AppPreviewResponse,
)
from app.services.app_store import app_service

from app.core.custom_route import CustomAPIRoute

router = APIRouter(prefix="/api/apps", tags=["apps"], route_class=CustomAPIRoute)


@router.get("", response_model=list[AppOut])
async def list_apps(
    category: str | None = None,
    tag: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出应用商店应用。"""
    return await app_service.list_apps(db, category=category, tag=tag)


@router.get("/{name}", response_model=AppDetailOut)
async def get_app(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取应用详情。"""
    app = await app_service.get_app(db, name)

    return {
        "id": app.id,
        "name": app.name,
        "display_name": app.display_name,
        "description": app.description,
        "category": app.category,
        "tags": app.tags,
        "icon": app.icon,
        "website": app.website,
        "source_url": app.source_url,
        "architectures": app.architectures,
        "image": app.image,
        "default_ports": app.default_ports,
        "config_schema": app.config_schema,
        "version": app.version,
        "is_builtin": app.is_builtin,
        "type": app.type,
        "changelog": app.changelog,
        "backup_paths": app.backup_paths,
        "source_dir": app.source_dir,
        "readme": app.readme or "",
    }


@router.get("/{name}/icon")
async def get_app_icon(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取应用图标。"""
    app = await app_service.get_app(db, name)
    if not app.icon:
        raise APIException("应用无图标", 404)

    icon_path = Path(app.icon)
    if not icon_path.is_absolute():
        icon_path = Path(__file__).parent.parent.parent / icon_path

    if not icon_path.exists():
        raise APIException("图标文件不存在", 404)

    return FileResponse(icon_path)


@router.post("/{name}/preview", response_model=AppPreviewResponse)
async def preview_app(
    name: str,
    data: AppDeployRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """预览应用渲染后的 Compose YAML。"""
    rendered_yaml = await app_service.preview(
        db,
        app_name=name,
        instance_name=data.instance_name,
        config=data.config,
    )
    return {"yaml": rendered_yaml}


@router.post("/{name}/deploy", response_model=AppDeployResponse)
async def deploy_app(
    name: str,
    data: AppDeployRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """一键部署应用。"""
    instance = await app_service.deploy(
        db,
        app_name=name,
        instance_name=data.instance_name,
        config=data.config,
        user_id=current_user.id,
    )

    project = instance.project
    stack = project.stack if project else None
    status_text = stack.status if stack else "unknown"

    pending = getattr(instance, "_pending_config", {})

    return AppDeployResponse(
        instance_id=instance.id,
        project_id=instance.project_id,
        project_name=project.project_name if project else "",
        instance_name=instance.instance_name,
        status=status_text,
        pending_config=pending,
    )
