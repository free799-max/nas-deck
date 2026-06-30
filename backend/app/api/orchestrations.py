"""应用编排 API 路由模块。

提供自动化分类组合模板的浏览与组合部署接口。
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
        "version": orchestration.version,
        "is_builtin": orchestration.is_builtin,
        "app_composition": orchestration.app_composition or [],
        "shared_config_schema": orchestration.shared_config_schema or {},
    }


@router.get("/{name}/icon")
async def get_orchestration_icon(
    name: str,
    db: AsyncSession = Depends(get_db),
):
    """获取应用编排图标（公开访问）。"""
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
    """组合部署应用编排。"""
    group, task_ids = await orchestration_service.deploy(
        db,
        orchestration_name=name,
        instance_name=data.instance_name,
        selected_apps=data.selected_apps,
        app_configs=data.app_configs,
        shared_config=data.shared_config,
        user_id=current_user.id,
    )

    return OrchestrationDeployResponse(
        group_id=group.id,
        instance_name=group.instance_name,
        status=group.status,
        task_ids=task_ids,
    )
