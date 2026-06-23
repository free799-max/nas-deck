"""Docker 宿主机信息相关 Pydantic Schema。"""

from pydantic import BaseModel


class DirectoryEntry(BaseModel):
    """目录条目信息。"""

    name: str
    path: str
    is_directory: bool


class DirectoryList(BaseModel):
    """目录列表响应。"""

    path: str
    entries: list[DirectoryEntry]


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
    disk_total: int  # 字节
    disk_used: int  # 字节
    disk_free: int  # 字节
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


class HostInfo(BaseModel):
    """Docker 宿主机综合信息。"""

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
