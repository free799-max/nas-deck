"""
Docker 容器管理 API 模块

提供 Docker 容器相关的管理接口，包括：
- 查询 Docker 服务是否可用
- 获取容器列表
- 获取单个容器详情
- 对容器执行操作（启动、停止、重启等）
- 获取容器日志

所有端点挂载在 /api/docker 路径下，需要用户已登录。
"""

import asyncio
import json
import threading
import queue

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import APIException
import docker

from app.models.user import User
from app.models.docker import DockerMirrorConfig
from app.schemas.docker import (
    ContainerInfo, ContainerAction, HostInfo,
    ImageInfo, ImageDetail, ImagePruneResult, ImageSearchResult,
    ImagePullRequest, ImageTag, PullTaskResponse, PullTaskStatus,
    RegistryCreate, RegistryUpdate, RegistryOut,
    BatchImageDeleteRequest,
)
from app.core.security import get_current_user, get_current_user_sse
from app.core.docker_manager import docker_manager, task_manager
from app.core.custom_route import CustomAPIRoute
from app.database import get_db

# 创建 Docker 管理路由器，路径前缀为 /api/docker，标签为 docker
router = APIRouter(prefix="/api/docker", tags=["docker"], route_class=CustomAPIRoute)


@router.get("/status")
async def docker_status(current_user: User = Depends(get_current_user)):
    """
    查询 Docker 服务状态

    返回当前系统中 Docker 服务是否可用。

    Args:
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        dict: 包含 available 字段，表示 Docker 是否可用
    """
    return {"available": docker_manager.available}


@router.get("/containers", response_model=list[ContainerInfo])
async def list_containers(current_user: User = Depends(get_current_user)):
    """
    获取所有容器列表

    返回当前 Docker 环境中所有容器的信息列表。

    Args:
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        list[ContainerInfo]: 容器信息列表
    """
    return docker_manager.list_containers()


@router.get("/containers/{container_id}", response_model=ContainerInfo)
async def get_container(container_id: str, current_user: User = Depends(get_current_user)):
    """
    获取单个容器的详细信息

    根据容器 ID 查询并返回该容器的详细信息。

    Args:
        container_id: 容器的 ID 或名称
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        ContainerInfo: 容器详细信息

    Raises:
        APIException: 当容器不存在时返回 404 错误
    """
    # 通过 docker_manager 查询容器
    container = docker_manager.get_container(container_id)
    if not container:
        raise APIException("容器不存在", 404)
    return container


@router.post("/containers/{container_id}/action", status_code=status.HTTP_204_NO_CONTENT)
async def container_action(
    container_id: str,
    data: ContainerAction,
    current_user: User = Depends(get_current_user),
):
    """
    对容器执行操作

    对指定容器执行操作，如启动（start）、停止（stop）、重启（restart）等。

    Args:
        container_id: 容器的 ID 或名称
        data: 容器操作请求数据，包含要执行的操作类型
        current_user: 当前登录用户（通过依赖注入获取）

    Raises:
        APIException: 当容器不存在时返回 404 错误
        APIException: 当操作执行失败时返回 500 错误
    """
    try:
        # 执行容器操作（如 start、stop、restart）
        docker_manager.container_action(container_id, data.action)
    except docker.errors.NotFound:
        # 容器不存在
        raise APIException("容器不存在", 404)
    except Exception as e:
        # 其他操作异常（如容器状态不允许该操作）
        raise APIException(f"容器操作失败: {e}", 500)


@router.get("/containers/{container_id}/logs")
async def container_logs(
    container_id: str,
    tail: int = 100,
    current_user: User = Depends(get_current_user),
):
    """
    获取容器日志

    获取指定容器的最近日志输出。

    Args:
        container_id: 容器的 ID 或名称
        tail: 返回最后 N 行日志，默认为 100 行
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        dict: 包含 logs 字段，为容器日志内容
    """
    # 获取容器的日志，tail 参数控制返回的行数
    logs = docker_manager.get_container_logs(container_id, tail=tail)
    return {"logs": logs}


@router.get("/host/info", response_model=HostInfo)
async def get_host_info(current_user: User = Depends(get_current_user)):
    """获取 Docker 宿主机综合信息。

    返回 Docker 宿主机的主机名、操作系统、架构、内核版本、
    Docker 引擎版本、资源信息、Docker 统计信息和网络列表。
    即使后端部署在 Docker 容器内，返回的也是宿主机的信息。

    Args:
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        HostInfo: 宿主机综合信息

    Raises:
        APIException: 当 Docker 服务不可用时返回 503 错误
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    info = docker_manager.get_host_info()
    if not info:
        raise APIException("Docker 不可用", 503)
    return info


# ===================== 镜像管理 =====================

@router.get("/images", response_model=list[ImageInfo])
async def list_images(current_user: User = Depends(get_current_user)):
    """获取本地镜像列表（扁平化，每行对应一个 tag）。

    Args:
        current_user: 当前登录用户

    Returns:
        list[ImageInfo]: 本地镜像列表
    """
    return docker_manager.list_images()


@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_image(
    image_id: str,
    force: bool = False,
    current_user: User = Depends(get_current_user),
):
    """删除指定镜像。

    Args:
        image_id: 镜像 ID 或标签
        force: 是否强制删除
        current_user: 当前登录用户

    Raises:
        APIException: 镜像不存在或删除失败
    """
    try:
        docker_manager.remove_image(image_id, force=force)
    except docker.errors.ImageNotFound:
        raise APIException("镜像不存在", 404)
    except docker.errors.APIError as e:
        raise APIException(f"删除镜像失败: {e}", 500)


@router.get("/images/{image_id}/detail", response_model=ImageDetail)
async def get_image_detail(
    image_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取镜像完整元数据。

    Args:
        image_id: 镜像完整 ID（sha256:...）或短 ID。
        current_user: 当前登录用户

    Returns:
        ImageDetail: 镜像元数据

    Raises:
        APIException: 镜像不存在时返回 404
        APIException: Docker 不可用时返回 503
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    detail = docker_manager.get_image_detail(image_id)
    if not detail:
        raise APIException("镜像不存在", 404)
    return detail


@router.post("/images/prune", response_model=ImagePruneResult)
async def prune_images(current_user: User = Depends(get_current_user)):
    """移除所有未使用的镜像。

    移除所有未被容器引用的镜像，包括有标签但无容器使用的镜像。

    Args:
        current_user: 当前登录用户

    Returns:
        ImagePruneResult: 被删除的镜像列表和释放空间

    Raises:
        APIException: Docker 不可用时返回 503
        APIException: 执行失败时返回 500
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    try:
        return docker_manager.prune_unused_images()
    except RuntimeError:
        raise APIException("Docker 不可用", 503)
    except Exception as e:
        raise APIException(f"移除未使用镜像失败: {e}", 500)


@router.get("/images/search")
async def search_images(
    q: str,
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """搜索镜像。

    使用当前默认配置的镜像搜索接口；无默认配置时使用 Docker Hub 官方 API。

    Args:
        q: 搜索关键词
        page: 页码，从 1 开始
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        dict: 包含 total、page、page_size、results 的分页结果

    Raises:
        APIException: 当所有镜像搜索源均不可用或解析失败时抛出
    """
    try:
        result = await db.execute(
            select(DockerMirrorConfig).where(DockerMirrorConfig.is_default == True)
        )
        config = result.scalar_one_or_none()
        if config:
            return docker_manager.search_images(
                q,
                page=page,
                api_url=config.search_api_url,
                mirror_url=config.mirror_url if config.enable_mirror else None,
                username=config.username,
                password=config.password,
            )
        # 无默认配置时使用 Docker Hub 官方 API
        return docker_manager.search_images(q, page=page)
    except RuntimeError as e:
        raise APIException(str(e), 503) from e
    except Exception as e:
        raise APIException(f"镜像搜索失败: {e}", 500) from e


@router.get("/images/tags", response_model=list[ImageTag])
async def get_image_tags(
    image: str,
    current_user: User = Depends(get_current_user),
):
    """获取指定镜像的可用标签列表。

    通过 Docker Hub API 查询镜像的所有可用 tags。

    Args:
        image: 镜像名称（不含标签，如 "nginx"）
        current_user: 当前登录用户

    Returns:
        list[ImageTag]: 标签列表
    """
    tags = docker_manager.get_image_tags(image)
    return tags


@router.post("/images/pull", response_model=PullTaskResponse)
async def pull_image(
    data: ImagePullRequest,
    current_user: User = Depends(get_current_user),
):
    """启动镜像拉取任务。

    在后台线程中流式拉取镜像，返回任务 ID 用于后续进度查询。

    Args:
        data: 拉取请求，包含镜像名称（含标签）
        current_user: 当前登录用户

    Returns:
        PullTaskResponse: 包含 task_id 和初始状态

    Raises:
        APIException: Docker 不可用时返回 503
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)

    try:
        task_id = task_manager.create_task(data.image)
    except RuntimeError as e:
        raise APIException(str(e), 429)

    # 在后台线程中执行拉取
    thread = threading.Thread(
        target=docker_manager.pull_image_async,
        args=(data.image, task_id, task_manager),
        daemon=True,
    )
    thread.start()

    return {
        "task_id": task_id,
        "image": data.image,
        "status": "pulling",
    }


@router.get("/images/pull/{task_id}/events")
async def pull_image_events(
    task_id: str,
    current_user: User = Depends(get_current_user_sse),
):
    """获取镜像拉取任务的实时进度（SSE）。

    建立 SSE 连接，先推送已缓存的进度，然后实时推送新进度。
    页面切换后重新连接可恢复进度。

    Args:
        task_id: 任务唯一标识
        current_user: 当前登录用户

    Returns:
        StreamingResponse: SSE 流

    Raises:
        APIException: 任务不存在时返回 404
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise APIException("任务不存在", 404)

    async def event_generator():
        """SSE 事件生成器。"""
        # 先发送已缓存的当前进度（已完成/失败时嵌入状态）
        _initial = task["progress"].copy()
        if task["status"] in ("completed", "failed"):
            _initial["_task_status"] = task["status"]
            if task.get("error"):
                _initial["_error"] = task["error"]
        yield f"data: {json.dumps(_initial, ensure_ascii=False)}\n\n"

        # 注册监听器队列接收实时更新
        q = task_manager.register_listener(task_id)
        try:
            while True:
                # 非阻塞取队列，超时 1 秒检查任务状态
                try:
                    progress = q.get(timeout=1)
                    yield f"data: {json.dumps(progress, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    pass

                # 检查任务是否已完成或失败
                current_task = task_manager.get_task(task_id)
                if not current_task:
                    break
                if current_task["status"] in ("completed", "failed"):
                    # 发送最终状态后关闭（嵌入状态便于前端同步）
                    _final = current_task["progress"].copy()
                    _final["_task_status"] = current_task["status"]
                    if current_task.get("error"):
                        _final["_error"] = current_task["error"]
                    yield f"data: {json.dumps(_final, ensure_ascii=False)}\n\n"
                    break

                # 让出控制权，避免阻塞
                await asyncio.sleep(0.1)
        finally:
            task_manager.unregister_listener(task_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/images/pull/{task_id}/status", response_model=PullTaskStatus)
async def pull_image_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取镜像拉取任务的当前状态。

    用于页面切换后恢复进度（不通过 SSE 时也可轮询）。

    Args:
        task_id: 任务唯一标识
        current_user: 当前登录用户

    Returns:
        PullTaskStatus: 任务完整状态

    Raises:
        APIException: 任务不存在时返回 404
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise APIException("任务不存在", 404)
    return task


# ===================== 镜像搜索接口配置（Registry） =====================


@router.get("/registries", response_model=list[RegistryOut])
async def list_registries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取所有镜像搜索接口配置列表。

    Args:
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        list[RegistryOut]: 配置列表
    """
    result = await db.execute(select(DockerMirrorConfig).order_by(DockerMirrorConfig.id))
    configs = result.scalars().all()
    return configs


@router.post("/registries", response_model=RegistryOut)
async def create_registry(
    data: RegistryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建镜像搜索接口配置。

    如果是第一条配置，自动设为默认。

    Args:
        data: 创建请求数据
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        RegistryOut: 创建后的配置
    """
    config = DockerMirrorConfig(
        name=data.name,
        search_api_url=data.search_api_url,
        mirror_url=data.mirror_url,
        enable_mirror=data.enable_mirror,
        username=data.username,
        password=data.password,
    )
    # 如果是第一条配置，自动设为默认
    count_result = await db.execute(select(DockerMirrorConfig))
    if not count_result.scalars().first():
        config.is_default = True
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@router.put("/registries/{registry_id}", response_model=RegistryOut)
async def update_registry(
    registry_id: int,
    data: RegistryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新镜像搜索接口配置。

    Args:
        registry_id: 配置记录 ID
        data: 更新请求数据
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        RegistryOut: 更新后的配置

    Raises:
        APIException: 配置不存在时返回 404
    """
    result = await db.execute(
        select(DockerMirrorConfig).where(DockerMirrorConfig.id == registry_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise APIException("配置不存在", 404)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)
    await db.commit()
    await db.refresh(config)
    return config


@router.delete("/registries/{registry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_registry(
    registry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除镜像搜索接口配置。

    默认配置不允许删除；删除默认配置前需先切换默认。

    Args:
        registry_id: 配置记录 ID
        db: 数据库会话
        current_user: 当前登录用户

    Raises:
        APIException: 配置不存在时返回 404
        APIException: 删除默认配置时返回 400
    """
    result = await db.execute(
        select(DockerMirrorConfig).where(DockerMirrorConfig.id == registry_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise APIException("配置不存在", 404)
    if config.is_default:
        raise APIException("默认配置不允许删除，请先切换默认配置", 400)
    await db.delete(config)
    await db.commit()


@router.post("/registries/{registry_id}/set-default", response_model=RegistryOut)
async def set_default_registry(
    registry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """将指定配置设为默认。

    会自动取消其他配置的默认状态。

    Args:
        registry_id: 配置记录 ID
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        RegistryOut: 更新后的配置

    Raises:
        APIException: 配置不存在时返回 404
    """
    result = await db.execute(
        select(DockerMirrorConfig).where(DockerMirrorConfig.id == registry_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise APIException("配置不存在", 404)
    # 取消其他配置的默认状态
    others = await db.execute(
        select(DockerMirrorConfig).where(
            DockerMirrorConfig.is_default == True,
            DockerMirrorConfig.id != registry_id,
        )
    )
    for other in others.scalars().all():
        other.is_default = False
    config.is_default = True
    await db.commit()
    await db.refresh(config)
    return config


# ===================== 批量删除 =====================


@router.post("/images/batch-delete")
async def batch_delete_images(
    data: BatchImageDeleteRequest,
    current_user: User = Depends(get_current_user),
):
    """批量删除本地镜像。

    Args:
        data: 批量删除请求，包含镜像 ID 列表和是否强制删除
        current_user: 当前登录用户

    Returns:
        dict: 包含 deleted 和 failed 两个列表的结果

    Raises:
        APIException: Docker 不可用或删除失败
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    if not data.ids:
        return {"deleted": [], "failed": []}
    try:
        result = docker_manager.remove_images(data.ids, force=data.force)
        return result
    except RuntimeError:
        raise APIException("Docker 不可用", 503)
    except Exception as e:
        raise APIException(f"批量删除镜像失败: {e}", 500)
