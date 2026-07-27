"""应用商店 API 路由模块。"""

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.app_store import (
    AppCreate,
    AppDeployRequest,
    AppDetailOut,
    AppOut,
    AppPreviewResponse,
    AppTemplatePreviewRequest,
    AppUpdate,
)
from app.schemas.orchestration.deploy_task import DeployTaskCreateResponse
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


@router.post("", response_model=AppDetailOut, status_code=201)
async def create_app(
    data: AppCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """创建应用商店应用（仅管理员）。"""
    return await app_service.create_app(db, data)


@router.post("/preview-template", response_model=AppPreviewResponse)
async def preview_template(
    data: AppTemplatePreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """预览未落库的应用模板渲染结果（仅管理员，创建/编辑页用）。"""
    return await app_service.preview_template(
        db,
        yaml_template=data.yaml_template,
        config_schema=data.config_schema,
        image=data.image,
        app_name=data.app_name,
    )


@router.get("/{name}", response_model=AppDetailOut)
async def get_app(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取应用详情。"""
    return await app_service.get_app(db, name)


@router.put("/{name}", response_model=AppDetailOut)
async def update_app(
    name: str,
    data: AppUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """更新应用商店应用（仅管理员，name 不可修改）。"""
    return await app_service.update_app(db, name, data)


@router.delete("/{name}", status_code=204)
async def delete_app(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """删除应用商店应用（仅管理员；内置应用与存在部署实例的应用禁止删除）。"""
    await app_service.delete_app(db, name)


@router.post("/{name}/icon", response_model=AppDetailOut)
async def upload_app_icon(
    name: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """上传应用图标（仅管理员），保存后 app.icon 指向后端图标接口。"""
    content = await file.read()
    return await app_service.save_app_icon(db, name, file.filename or "", content)


@router.get("/{name}/icon")
async def get_app_icon(name: str):
    """获取用户上传的应用图标文件。

    无需认证：<img> 标签无法携带 Bearer token，且图标为非敏感静态资源。
    """
    icon_path = app_service.get_app_icon_path(name)
    return FileResponse(icon_path)


@router.post("/{name}/preview", response_model=AppPreviewResponse)
async def preview_app(
    name: str,
    data: AppDeployRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """预览应用渲染后的 Compose YAML。"""
    result = await app_service.preview(
        db,
        app_name=name,
        instance_name=data.instance_name,
        config=data.config,
    )
    return result


@router.post("/{name}/deploy", response_model=DeployTaskCreateResponse)
async def deploy_app(
    name: str,
    data: AppDeployRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """一键部署应用，返回部署任务 ID。"""
    instance, task_id = await app_service.deploy(
        db,
        app_name=name,
        instance_name=data.instance_name,
        config=data.config,
        user_id=current_user.id,
    )

    return DeployTaskCreateResponse(
        task_id=task_id,
        instance_id=instance.id,
        status="deploying",
    )
