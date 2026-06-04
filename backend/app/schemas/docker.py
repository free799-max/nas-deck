"""Docker 容器相关的 Pydantic Schema 模块。

定义容器管理模块的请求/响应数据模型：
- ContainerInfo: 容器信息的响应数据
- ContainerAction: 容器操作的请求数据
- DockerVersionInfo: Docker 版本信息
- ResourceInfo: 宿主机资源信息
- DockerStatsInfo: Docker 统计信息
- NetworkInfo: Docker 网络信息
- HostInfo: 宿主机综合信息
"""

from typing import Literal

from pydantic import BaseModel


class ContainerInfo(BaseModel):
    """
    容器信息响应数据模型。

    用于序列化返回给客户端的 Docker 容器基本信息。

    Attributes:
        id: 容器 ID（Docker 引擎中的哈希字符串）
        name: 容器名称
        status: 容器运行状态（如 running、exited 等）
        health: 容器健康检查状态（如 healthy、unhealthy 等）
        image: 容器所使用的镜像名称
    """

    id: str  # 容器 ID
    name: str  # 容器名称
    status: str  # 运行状态
    health: str  # 健康检查状态
    image: str  # 使用的镜像名称


class ContainerAction(BaseModel):
    """
    容器操作请求数据模型。

    用于校验容器控制接口的请求参数，只允许 start、stop、restart 三种操作。

    Attributes:
        action: 要执行的操作，限定为 "start"、"stop" 或 "restart"
    """

    action: Literal["start", "stop", "restart"]  # 操作类型，限定三种取值


class DockerVersionInfo(BaseModel):
    """Docker 引擎版本信息。"""

    version: str
    api_version: str
    go_version: str
    os: str
    arch: str
    kernel_version: str
    build_time: str


class ResourceInfo(BaseModel):
    """宿主机资源信息（CPU、内存、磁盘）。"""

    cpu_cores: int
    memory_total: int  # 字节
    disk_total: int    # 字节
    disk_used: int     # 字节
    disk_free: int     # 字节
    disk_usage_percent: float


class DockerStatsInfo(BaseModel):
    """Docker 统计信息（容器、镜像数量）。"""

    containers_total: int
    containers_running: int
    containers_paused: int
    containers_stopped: int
    images: int


class NetworkInfo(BaseModel):
    """Docker 网络信息。"""

    id: str
    name: str
    driver: str
    scope: str


class ImageInfo(BaseModel):
    """本地 Docker 镜像信息。

    Attributes:
        id: 镜像短 ID（12 位）
        tags: 镜像标签列表（如 ["nginx:latest", "nginx:alpine"]）
        size: 镜像大小（字节）
        created: 创建时间（ISO 8601 格式）
        containers: 使用该镜像的容器数量（-1 表示未知）
    """

    id: str
    tags: list[str]
    size: int
    created: str
    containers: int


class ImageSearchResult(BaseModel):
    """Docker Hub 镜像搜索结果。

    Attributes:
        name: 镜像完整名称（如 "library/nginx"）
        description: 镜像描述
        star_count: Star 数量
        official: 是否为官方镜像
    """

    name: str
    description: str
    star_count: int
    official: bool


class ImagePullRequest(BaseModel):
    """镜像拉取请求。

    Attributes:
        image: 要拉取的镜像名称（含标签，如 "nginx:latest"）
    """

    image: str


class HostInfo(BaseModel):
    """Docker 宿主机综合信息。

    包含主机名、操作系统、架构、内核版本、Docker 版本、资源、统计、存储和网络信息。
    """

    hostname: str
    os: str
    arch: str
    kernel_version: str
    docker_version: DockerVersionInfo
    resources: ResourceInfo
    stats: DockerStatsInfo
    storage_driver: str
    docker_root_dir: str
    networks: list[NetworkInfo]
