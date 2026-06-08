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

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import APIException
import docker

from app.models.user import User
from app.models.docker import DockerMirrorConfig
from app.schemas.docker import (
    ContainerInfo, ContainerAction, HostInfo,
    ImageInfo, ImageSearchResult, ImagePullRequest,
    RegistryCreate, RegistryUpdate, RegistryOut,
    BatchImageDeleteRequest,
)
from app.core.security import get_current_user
from app.core.docker_manager import docker_manager
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
    """获取本地镜像列表。

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


@router.get("/images/search", response_model=list[ImageSearchResult])
async def search_images(
    q: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """搜索镜像。

    使用当前默认配置的镜像搜索接口；无默认配置时使用 Docker Hub 官方 API。

    Args:
        q: 搜索关键词
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        list[ImageSearchResult]: 搜索结果列表
    """
    result = await db.execute(
        select(DockerMirrorConfig).where(DockerMirrorConfig.is_default == True)
    )
    config = result.scalar_one_or_none()
    if config:
        return docker_manager.search_images(
            q,
            api_url=config.search_api_url,
            mirror_url=config.mirror_url if config.enable_mirror else None,
            username=config.username,
            password=config.password,
        )
    # 无默认配置时使用 Docker Hub 官方 API
    return docker_manager.search_images(q)


@router.post("/images/pull", status_code=status.HTTP_204_NO_CONTENT)
async def pull_image(
    data: ImagePullRequest,
    current_user: User = Depends(get_current_user),
):
    """拉取指定镜像。

    Args:
        data: 拉取请求，包含镜像名称
        current_user: 当前登录用户

    Raises:
        APIException: 拉取失败
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    try:
        docker_manager.pull_image(data.image)
    except docker.errors.ImageNotFound:
        raise APIException("镜像不存在", 404)
    except docker.errors.APIError as e:
        raise APIException(f"拉取镜像失败: {e}", 500)
    except Exception as e:
        raise APIException(f"拉取镜像失败: {e}", 500)


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
