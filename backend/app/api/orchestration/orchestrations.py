"""应用编排 API 路由模块。

提供自动化分类组合模板的浏览与组合部署接口。
"""

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import APIException
from app.core.security import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.models.orchestration import AppOrchestrationInstance
from app.schemas.app_auth import (
    AppAuthVerifyRequest,
    AppAuthVerifyResponse,
)
from app.schemas.orchestration import (
    InspectFixRequest,
    OrchestrationBackupOut,
    OrchestrationDeleteResponse,
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
    OrchestrationRestoreRequest,
    PluginInstallRequest,
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
    current_user: User = Depends(require_admin),
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


@router.delete(
    "/instances/{instance_id}", response_model=OrchestrationDeleteResponse
)
async def delete_orchestration_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """删除编排实例组：创建后台任务，进度通过部署任务 SSE 推送。

    容器与 Compose 项目会被移除，各应用数据目录移入备份目录。
    """
    task_id = await orchestration_service.start_delete_instance(db, instance_id)
    return OrchestrationDeleteResponse(task_id=task_id)


@router.post("/instances/{instance_id}/redeploy", response_model=OrchestrationDeployResponse)
async def redeploy_orchestration_instance(
    instance_id: int,
    data: OrchestrationDeployRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """重新部署编排实例组：清理旧实例与项目后按原路径重新部署。"""
    group, task_ids = await orchestration_service.redeploy_instance(
        db,
        group_id=instance_id,
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


@router.post("/instances/{instance_id}/wire")
async def wire_orchestration_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """手动重跑自动装配：把来源应用（下载器/媒体服务器）配置进目标应用。

    后台协程执行，立即返回；装配结果写入实例组 app_configs 的 integrations 字段。
    """
    # 校验实例组存在（不存在抛 404）
    await orchestration_service.get_group(db, instance_id)
    orchestration_service.schedule_wiring(instance_id)
    return {"ok": True, "message": "装配已开始"}


@router.get("/backups", response_model=list[OrchestrationBackupOut])
async def list_orchestration_backups(
    orchestration: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """列出可恢复的实例组备份（删除时自动生成）。"""
    return await orchestration_service.list_backups(db, orchestration)


@router.post("/backups/restore", response_model=OrchestrationDeployResponse)
async def restore_orchestration_backup(
    data: OrchestrationRestoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """从备份恢复实例组：移回应用数据目录并按原配置重新部署。"""
    group, task_ids = await orchestration_service.restore_backup(
        db,
        backup_name=data.backup,
        instance_name=data.instance_name,
        user_id=current_user.id,
    )
    return OrchestrationDeployResponse(
        group_id=group.id,
        instance_name=group.instance_name,
        status=group.status,
        task_ids=task_ids,
    )


@router.get("/instances/{instance_id}/apps/{app_name}/inspect")
async def inspect_orchestration_app(
    instance_id: int,
    app_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """对组内指定应用执行配置健康检测。

    应用不支持检测时返回 supported=false 而非报错。
    """
    report = await orchestration_service.inspect_app(db, instance_id, app_name)
    return {
        "supported": report.supported,
        "items": [asdict(item) for item in report.items],
    }


@router.post("/instances/{instance_id}/apps/{app_name}/inspect/fix")
async def fix_orchestration_app(
    instance_id: int,
    app_name: str,
    data: InspectFixRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """对组内指定应用的检测项执行自动修复。"""
    results = await orchestration_service.apply_fixes(
        db, instance_id, app_name, data.item_ids
    )
    return {"results": [asdict(item) for item in results]}


@router.get("/instances/{instance_id}/apps/{app_name}/plugins")
async def list_app_plugins(
    instance_id: int,
    app_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """查询应用已安装插件与插件市场列表（当前仅 MoviePilot 支持）。"""
    return await orchestration_service.list_app_plugins(db, instance_id, app_name)


@router.post("/instances/{instance_id}/apps/{app_name}/plugins/install")
async def install_app_plugin(
    instance_id: int,
    app_name: str,
    data: PluginInstallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """安装应用插件（当前仅 MoviePilot 支持）。"""
    await orchestration_service.install_app_plugin(
        db, instance_id, app_name, data.plugin_id, repo_url=data.repo_url
    )
    return {"ok": True, "message": "插件安装成功"}


@router.post("/auth/verify", response_model=AppAuthVerifyResponse)
async def verify_app_auth(
    data: AppAuthVerifyRequest,
    current_user: User = Depends(require_admin),
):
    """验证应用访问地址与认证信息。"""
    result = await orchestration_service.verify_app_auth(
        app_name=data.app_name,
        config=data.model_dump(),
    )
    return AppAuthVerifyResponse(valid=result.valid, message=result.message)


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
        # icon 字段约定为相对 backend/ 的路径（如 data/icons/media-stack.svg）
        backend_dir = Path(__file__).resolve().parent.parent.parent.parent
        icon_path = backend_dir / icon_path
    icon_path = icon_path.resolve()

    # 只允许提供图标目录内的文件，防止通过 icon 字段读取任意宿主机文件
    allowed_dirs = [
        Path(settings.APP_ICON_DIR).resolve(),
        (Path(settings.DATA_ROOT) / "icons").resolve(),
    ]
    if not any(icon_path.is_relative_to(d) for d in allowed_dirs):
        raise APIException("图标文件不存在", 404)

    if not icon_path.exists():
        raise APIException("图标文件不存在", 404)

    return FileResponse(icon_path)


@router.post("/{name}/deploy", response_model=OrchestrationDeployResponse)
async def deploy_orchestration(
    name: str,
    data: OrchestrationDeployRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
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
    current_user: User = Depends(require_admin),
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
