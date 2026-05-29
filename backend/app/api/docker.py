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

from fastapi import APIRouter, Depends

from app.core.exceptions import APIException
import docker

from app.models.user import User
from app.schemas.docker import ContainerInfo, ContainerAction, HostInfo
from app.core.security import get_current_user
from app.core.docker_manager import docker_manager

# 创建 Docker 管理路由器，路径前缀为 /api/docker，标签为 docker
router = APIRouter(prefix="/api/docker", tags=["docker"])


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


@router.post("/containers/{container_id}/action")
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

    Returns:
        dict: 包含 success 字段，表示操作是否成功

    Raises:
        APIException: 当容器不存在时返回 404 错误
        APIException: 当操作执行失败时返回 500 错误
    """
    try:
        # 执行容器操作（如 start、stop、restart）
        docker_manager.container_action(container_id, data.action)
        return {"success": True}
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
