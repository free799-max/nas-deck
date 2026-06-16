"""Docker Compose 编排相关 API。"""

import asyncio
import json as _json
import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.custom_route import CustomAPIRoute
from app.core.exceptions import APIException
from app.core.security import get_current_user, get_current_user_sse
from app.database import get_db
from app.models.docker import DockerComposeProject, DockerComposeStack, DockerComposeVersion
from app.models.user import User
from app.schemas.docker import (
    ComposeActionRequest,
    ComposeEditRequest,
    ComposeProjectCreate,
    ComposeProjectOut,
    ComposeProjectUpdate,
    ComposeStackStatusOut,
    ComposeVersionCreate,
    ComposeVersionOut,
    ContainerInfo,
)
from app.core.compose_manager import compose_manager
from app.core.docker_manager import docker_manager

logger = logging.getLogger(__name__)
router = APIRouter(route_class=CustomAPIRoute)


def _build_version_out(version: DockerComposeVersion | None) -> ComposeVersionOut | None:
    """将版本模型转换为响应 schema。"""
    if not version:
        return None
    return ComposeVersionOut(
        id=version.id,
        version_number=version.version_number,
        content=version.content,
        comment=version.comment,
        is_current=version.is_current,
        created_by_user_id=version.created_by_user_id,
        created_at=version.created_at.isoformat() if version.created_at else "",
    )


def _build_stack_out(
    stack: DockerComposeStack | None,
    status_info: dict | None = None,
) -> ComposeStackStatusOut | None:
    """将 Stack 状态模型转换为响应 schema。"""
    if status_info is not None:
        ports = sorted(status_info.get("ports", []))
        return ComposeStackStatusOut(
            status=status_info.get("status", "unknown"),
            service_count=status_info.get("service_count", 0),
            running_count=status_info.get("running_count", 0),
            ports=ports,
            last_action=stack.last_action if stack else None,
            last_action_at=stack.last_action_at.isoformat() if stack and stack.last_action_at else None,
            updated_at=stack.updated_at.isoformat() if stack and stack.updated_at else "",
        )
    if not stack:
        return None
    ports = []
    if stack.ports:
        try:
            ports = _json.loads(stack.ports)
        except _json.JSONDecodeError:
            ports = []
    return ComposeStackStatusOut(
        status=stack.status,
        service_count=stack.service_count,
        running_count=stack.running_count,
        ports=ports,
        last_action=stack.last_action,
        last_action_at=stack.last_action_at.isoformat() if stack.last_action_at else None,
        updated_at=stack.updated_at.isoformat() if stack.updated_at else "",
    )


def _build_project_out(
    project: DockerComposeProject,
    status_info: dict | None = None,
) -> ComposeProjectOut:
    """将项目模型转换为响应 schema。"""
    current_version = None
    for version in project.versions:
        if version.is_current:
            current_version = version
            break
    config_files = []
    if project.config_files:
        try:
            config_files = _json.loads(project.config_files)
        except _json.JSONDecodeError:
            config_files = []
    return ComposeProjectOut(
        id=project.id,
        project_name=project.project_name,
        description=project.description,
        is_active=project.is_active,
        current_version=_build_version_out(current_version),
        stack=_build_stack_out(project.stack, status_info=status_info),
        config_files=config_files or None,
        working_dir=project.working_dir,
        created_at=project.created_at.isoformat() if project.created_at else "",
        updated_at=project.updated_at.isoformat() if project.updated_at else "",
    )


async def _get_compose_project(
    db: AsyncSession, project_id: int
) -> DockerComposeProject:
    """获取项目，不存在时抛出 404。"""
    result = await db.execute(
        select(DockerComposeProject)
        .options(
            selectinload(DockerComposeProject.versions),
            selectinload(DockerComposeProject.stack),
        )
        .where(DockerComposeProject.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise APIException("编排项目不存在", 404)
    return project


@router.get("/compose", response_model=list[ComposeProjectOut])
async def list_compose_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取所有 Compose 项目列表。"""
    await compose_manager.discover_projects(db)

    result = await db.execute(
        select(DockerComposeProject)
        .options(
            selectinload(DockerComposeProject.versions),
            selectinload(DockerComposeProject.stack),
        )
        .order_by(DockerComposeProject.id.desc())
    )
    projects = result.scalars().all()

    async def _project_with_status(project: DockerComposeProject) -> ComposeProjectOut:
        try:
            status_info = await compose_manager.get_status(project)
        except Exception:
            status_info = None
        return _build_project_out(project, status_info=status_info)

    return await asyncio.gather(*[_project_with_status(p) for p in projects])


@router.post("/compose", response_model=ComposeProjectOut, status_code=status.HTTP_201_CREATED)
async def create_compose_project(
    data: ComposeProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建 Compose 项目。"""
    try:
        project = await compose_manager.create_project(
            db,
            project_name=data.project_name,
            content=data.content,
            user_id=current_user.id,
            description=data.description,
        )
    except IntegrityError:
        await db.rollback()
        raise APIException("项目名已存在", 409)
    except ValueError as e:
        raise APIException(str(e), 400)
    except Exception as e:
        raise APIException(f"创建项目失败: {e}", 500)

    project = await _get_compose_project(db, project.id)
    return _build_project_out(project)


@router.get("/compose/{project_id}", response_model=ComposeProjectOut)
async def get_compose_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单个 Compose 项目详情。"""
    project = await _get_compose_project(db, project_id)
    return _build_project_out(project)


@router.put("/compose/{project_id}", response_model=ComposeProjectOut)
async def update_compose_project(
    project_id: int,
    data: ComposeProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新 Compose 项目元数据。"""
    project = await _get_compose_project(db, project_id)
    try:
        project = await compose_manager.update_project(
            db,
            project,
            description=data.description,
            is_active=data.is_active,
        )
    except Exception as e:
        raise APIException(f"更新项目失败: {e}", 500)
    return _build_project_out(project)


@router.post("/compose/{project_id}/edit", response_model=ComposeProjectOut)
async def edit_compose_project(
    project_id: int,
    data: ComposeEditRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑 Compose 项目并自动部署。"""
    project = await _get_compose_project(db, project_id)
    try:
        await compose_manager.edit_and_deploy(
            db,
            project,
            content=data.content,
            user_id=current_user.id,
            comment=data.comment,
            description=data.description,
        )
    except ValueError as e:
        raise APIException(str(e), 400)
    except RuntimeError as e:
        raise APIException(str(e), 500)
    except Exception as e:
        raise APIException(f"编辑部署失败: {e}", 500)

    project = await _get_compose_project(db, project_id)
    return _build_project_out(project)


@router.delete("/compose/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_compose_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除 Compose 项目。"""
    project = await _get_compose_project(db, project_id)
    try:
        await compose_manager.delete_project(db, project)
    except Exception as e:
        raise APIException(f"删除项目失败: {e}", 500)


@router.get("/compose/{project_id}/versions", response_model=list[ComposeVersionOut])
async def list_compose_versions(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取项目的所有版本列表。"""
    project = await _get_compose_project(db, project_id)
    return [_build_version_out(v) for v in project.versions]


@router.post("/compose/{project_id}/versions", response_model=ComposeVersionOut)
async def create_compose_version(
    project_id: int,
    data: ComposeVersionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """为项目新增一个版本。"""
    project = await _get_compose_project(db, project_id)
    try:
        version = await compose_manager.add_version(
            db,
            project,
            content=data.content,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise APIException(str(e), 400)
    except Exception as e:
        raise APIException(f"新增版本失败: {e}", 500)
    return _build_version_out(version)


@router.post("/compose/{project_id}/versions/{version_id}/rollback", response_model=ComposeVersionOut)
async def rollback_compose_version(
    project_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """切换到指定版本。"""
    project = await _get_compose_project(db, project_id)
    version = next((v for v in project.versions if v.id == version_id), None)
    if not version:
        raise APIException("版本不存在", 404)
    try:
        version = await compose_manager.rollback_version(db, project, version)
    except RuntimeError as e:
        raise APIException(str(e), 500)
    except Exception as e:
        raise APIException(f"切换版本失败: {e}", 500)
    return _build_version_out(version)


@router.post("/compose/{project_id}/action")
async def compose_action(
    project_id: int,
    data: ComposeActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """对 Compose 项目执行 up / down / restart 操作。"""
    project = await _get_compose_project(db, project_id)
    try:
        result = await compose_manager.action(db, project, data.action)
    except ValueError as e:
        raise APIException(str(e), 400)
    except RuntimeError as e:
        raise APIException(str(e), 500)
    except Exception as e:
        raise APIException(f"操作失败: {e}", 500)
    return {"success": True, "message": result["stdout"] or "ok"}


@router.get("/compose/{project_id}/status", response_model=ComposeStackStatusOut)
async def compose_status(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Compose 项目实时 Stack 状态。"""
    project = await _get_compose_project(db, project_id)
    try:
        stack = await compose_manager.sync_stack_status(db, project)
    except Exception as e:
        raise APIException(f"获取状态失败: {e}", 500)
    return _build_stack_out(stack)


@router.get("/compose/{project_id}/containers", response_model=list[ContainerInfo])
async def list_compose_containers(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Compose 项目维护的容器列表。"""
    project = await _get_compose_project(db, project_id)
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    filters = {"label": [f"com.docker.compose.project={project.project_name}"]}
    return docker_manager.list_containers(filters=filters)


@router.get("/compose/{project_id}/logs")
async def compose_logs(
    project_id: int,
    tail: int = 100,
    services: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Compose 项目日志。"""
    project = await _get_compose_project(db, project_id)
    service_list = services.split(",") if services else None
    try:
        logs = await compose_manager.get_logs(
            project, tail=tail, services=service_list
        )
    except RuntimeError as e:
        raise APIException(str(e), 500)
    except Exception as e:
        raise APIException(f"获取日志失败: {e}", 500)
    return {"logs": logs}


@router.get("/compose/{project_id}/logs/stream")
async def compose_logs_stream(
    project_id: int,
    tail: int = 100,
    follow: bool = True,
    services: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sse),
):
    """流式获取 Compose 项目日志（SSE）。"""
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)

    project = await _get_compose_project(db, project_id)
    service_list = services.split(",") if services else None

    async def event_generator():
        try:
            async for line in compose_manager.stream_logs(
                project, tail=tail, services=service_list, follow=follow
            ):
                yield f"data: {_json.dumps({'line': line}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("Compose 日志流异常")
            yield f"data: {_json.dumps({'error': f'日志流异常: {e}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
