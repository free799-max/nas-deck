"""应用编排 API 路由模块。

提供应用编排的浏览与一键部署接口。
"""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import APIException
from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.orchestration import (
    OrchestrationDeployRequest,
    OrchestrationDeployResponse,
    OrchestrationDetailOut,
    OrchestrationOut,
)
from app.services.orchestration import orchestration_service

from app.core.custom_route import CustomAPIRoute

router = APIRouter(prefix="/api/orchestrations", tags=["orchestrations"], route_class=CustomAPIRoute)


@router.get("", response_model=list[OrchestrationOut])
async def list_orchestrations(
    category: str | None = None,
    tag: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出所有应用编排。"""
    return await orchestration_service.list_orchestrations(db, category=category, tag=tag)


@router.get("/{name}", response_model=OrchestrationDetailOut)
async def get_orchestration(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取应用编排详情。"""
    orchestration = await orchestration_service.get_orchestration(db, name)
    return {
        "id": orchestration.id,
        "name": orchestration.name,
        "display_name": orchestration.display_name,
        "description": orchestration.description,
        "category": orchestration.category,
        "tags": orchestration.tags,
        "icon": orchestration.icon,
        "website": orchestration.website,
        "source_url": orchestration.source_url,
        "architectures": orchestration.architectures,
        "config_schema": orchestration.config_schema,
        "version": orchestration.version,
        "is_builtin": orchestration.is_builtin,
        "type": orchestration.type,
        "changelog": orchestration.changelog,
        "backup_paths": orchestration.backup_paths,
        "source_dir": orchestration.source_dir,
        "readme": orchestration.readme,
        "suggested_plugins": orchestration.suggested_plugins or [],
    }


@router.get("/{name}/icon")
async def get_orchestration_icon(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取应用编排图标。"""
    orchestration = await orchestration_service.get_orchestration(db, name)
    if not orchestration.icon:
        raise APIException("编排无图标", 404)

    icon_path = Path(orchestration.icon)
    if not icon_path.is_absolute():
        icon_path = Path(__file__).parent.parent.parent / icon_path

    if not icon_path.exists():
        raise APIException("图标文件不存在", 404)

    return FileResponse(icon_path)


@router.post("/{name}/deploy", response_model=OrchestrationDeployResponse)
async def deploy_orchestration(
    name: str,
    data: OrchestrationDeployRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """一键部署应用编排。"""
    instance = await orchestration_service.deploy(
        db,
        orchestration_name=name,
        instance_name=data.instance_name,
        config=data.config,
        user_id=current_user.id,
    )

    project = instance.project
    stack = project.stack
    status_text = stack.status if stack else "unknown"

    pending = getattr(instance, "_pending_config", {})

    return OrchestrationDeployResponse(
        instance_id=instance.id,
        project_id=project.id,
        project_name=project.project_name,
        instance_name=instance.instance_name,
        status=status_text,
        pending_config=pending,
    )
