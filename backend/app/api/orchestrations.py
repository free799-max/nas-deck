"""应用编排 API 路由模块。

提供自动化分类组合模板的浏览与组合部署接口。
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import APIException
from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.orchestration import AppOrchestrationInstance
from app.schemas.orchestration import (
    OrchestrationDeployRequest,
    OrchestrationDeployResponse,
    OrchestrationDetailOut,
    OrchestrationImportRequest,
    OrchestrationImportResponse,
    OrchestrationInstanceAppOut,
    OrchestrationInstanceDetailOut,
    OrchestrationInstanceGroupOut,
    OrchestrationInstanceUpdateRequest,
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


@router.get("/instances", response_model=list[OrchestrationInstanceGroupOut])
async def list_orchestration_instances(
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出当前用户的编排实例组（一次部署/导入记录）。"""
    groups = await orchestration_service.list_instances(db, category=category)
    return [
        OrchestrationInstanceGroupOut(
            id=g.id,
            instance_name=g.instance_name,
            orchestration_name=g.orchestration.name,
            orchestration_display_name=g.orchestration.display_name,
            status=g.status,
            created_at=g.created_at,
            apps=[
                OrchestrationInstanceAppOut(
                    id=inst.id,
                    app_name=inst.app.name if inst.app else inst.instance_name,
                    display_name=inst.app.display_name if inst.app else inst.instance_name,
                    icon=inst.app.icon if inst.app else None,
                    status=inst.status,
                    config=inst.config or {},
                )
                for inst in g.instances
            ],
        )
        for g in groups
    ]


def _build_instance_detail_out(
    group: AppOrchestrationInstance,
) -> dict:
    """将 AppOrchestrationInstance 转换为详情响应字典。"""
    return {
        "id": group.id,
        "instance_name": group.instance_name,
        "orchestration_name": group.orchestration.name,
        "orchestration_display_name": group.orchestration.display_name,
        "status": group.status,
        "created_at": group.created_at,
        "shared_config": group.shared_config or {},
        "app_configs": group.app_configs or {},
        "apps": [
            OrchestrationInstanceAppOut(
                id=inst.id,
                app_name=inst.app.name if inst.app else inst.instance_name,
                display_name=inst.app.display_name if inst.app else inst.instance_name,
                icon=inst.app.icon if inst.app else None,
                status=inst.status,
                config=inst.config or {},
            )
            for inst in group.instances
        ],
    }


@router.get("/instances/{instance_id}", response_model=OrchestrationInstanceDetailOut)
async def get_orchestration_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取编排实例组详情。"""
    group = await orchestration_service.get_instance_detail(db, instance_id)
    return _build_instance_detail_out(group)


@router.patch("/instances/{instance_id}", response_model=OrchestrationInstanceDetailOut)
async def update_orchestration_instance(
    instance_id: int,
    data: OrchestrationInstanceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新编排实例组信息。"""
    group = await orchestration_service.update_instance(
        db,
        instance_id,
        instance_name=data.instance_name,
        shared_config=data.shared_config,
        app_configs=data.app_configs,
    )
    return _build_instance_detail_out(group)


@router.delete("/instances/{instance_id}", status_code=204)
async def delete_orchestration_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除编排实例组及其关联实例。"""
    await orchestration_service.delete_instance(db, instance_id)
    return Response(status_code=204)


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


@router.get("/{name}/import-candidates")
async def get_import_candidates(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """扫描当前运行中的 Docker 容器，返回可导入的应用候选列表。"""
    candidates = await orchestration_service.scan_import_candidates(db, name)
    return [candidate.model_dump() for candidate in candidates]


@router.post("/{name}/import", response_model=OrchestrationImportResponse)
async def import_orchestration(
    name: str,
    data: OrchestrationImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导入已有 Docker 部署为应用编排实例。"""
    group, created_instance_ids = await orchestration_service.import_orchestration(
        db,
        orchestration_name=name,
        instance_name=data.instance_name,
        selected_apps=data.selected_apps,
        app_configs={
            app_name: config.model_dump(exclude_none=True)
            for app_name, config in data.app_configs.items()
        },
        shared_config=data.shared_config,
        user_id=current_user.id,
    )
    return OrchestrationImportResponse(
        group_id=group.id,
        instance_name=group.instance_name,
        status=group.status,
        created_app_instance_ids=created_instance_ids,
    )
