"""Docker 容器相关的 Pydantic Schema 模块。

定义容器管理模块的请求/响应数据模型：
- ContainerInfo: 容器信息的响应数据
- ContainerAction: 容器操作的请求数据
- DockerVersionInfo: Docker 版本信息
- ResourceInfo: 宿主机资源信息
- DockerStatsInfo: Docker 统计信息
- NetworkInfo: Docker 网络信息
- HostInfo: 宿主机综合信息
- MirrorConfig: 镜像查询配置
- BatchImageDeleteRequest: 批量删除镜像请求
"""

from datetime import datetime
from typing import Literal

import json
from pydantic import BaseModel, field_serializer, field_validator


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
    image: str  # 使用的镜像


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
    """本地 Docker 镜像信息（扁平化，每行对应一个 tag）。

    Attributes:
        id: 镜像短 ID（12 位，展示用）
        image_id: 镜像完整 ID（sha256:...，删除操作使用）
        name: Repository 名称（如 "nginx"）
        tag: Tag（如 "latest"）
        full_tag: 完整标签（如 "nginx:latest"）
        size: 镜像大小（字节）
        created: 创建时间（ISO 8601 格式）
        containers: 使用该镜像的容器数量
    """

    id: str
    image_id: str
    name: str
    tag: str
    full_tag: str
    size: int
    created: str
    containers: int


class ImageLayer(BaseModel):
    """镜像层信息（用于详情弹窗表格展示）。

    Attributes:
        order: 层序号
        size: 层大小（字节）
        layer: 层构建命令或描述
    """

    order: int
    size: int
    layer: str


class ImageDetail(BaseModel):
    """Docker 镜像完整元数据。

    Attributes:
        id: 镜像完整 ID
        name: Repository 名称
        tag: Tag
        full_tag: 完整标签
        size: 镜像大小（字节）
        created: 创建时间
        architecture: 架构（如 "amd64"）
        os: 操作系统（如 "linux"）
        cmd: 默认命令
        entrypoint: 入口点
        env: 环境变量列表
        exposed_ports: 暴露端口列表
        volumes: 卷列表
        working_dir: 工作目录
        user: 运行用户
        labels: 标签键值对
        layers: 镜像层 sha256 列表
        history: 构建历史命令列表
        parent: 父镜像 ID
        docker_version: Docker 构建版本
        build: 组合构建信息（Docker 版本 + OS + 架构）
        layers_table: 镜像层表格数据（带 size 和命令）
    """

    id: str
    name: str
    tag: str
    full_tag: str
    size: int
    created: str
    architecture: str
    os: str
    cmd: list[str] | None = None
    entrypoint: list[str] | None = None
    env: list[str] | None = None
    exposed_ports: list[str] | None = None
    volumes: list[str] | None = None
    working_dir: str | None = None
    user: str | None = None
    labels: dict[str, str] | None = None
    layers: list[str] | None = None
    history: list[str] | None = None
    parent: str | None = None
    docker_version: str | None = None
    build: str | None = None
    layers_table: list[ImageLayer] | None = None


class ImagePruneResult(BaseModel):
    """移除未使用镜像的结果。

    Attributes:
        deleted: 被删除的镜像/标签描述列表
        space_reclaimed: 释放空间（字节）
    """

    deleted: list[str]
    space_reclaimed: int


class ImageSearchResult(BaseModel):
    """Docker Hub 镜像搜索结果。

    Attributes:
        name: 镜像完整名称（如 "library/nginx"）
        description: 镜像描述
        star_count: Star 数量
        pull_count: 拉取次数
        official: 是否为官方镜像
        is_automated: 是否为自动构建镜像
    """

    name: str
    description: str
    star_count: int
    pull_count: int
    official: bool
    is_automated: bool


class ImagePullRequest(BaseModel):
    """镜像拉取请求。

    Attributes:
        image: 要拉取的镜像名称（含标签，如 "nginx:latest"）
    """

    image: str


class ImageTag(BaseModel):
    """镜像标签信息。

    Attributes:
        name: 标签名称（如 "latest"）
        last_updated: 最后更新时间
        size: 镜像大小（字节）
        digest: 镜像摘要
    """

    name: str
    last_updated: str
    size: int
    digest: str


class PullTaskResponse(BaseModel):
    """启动拉取任务响应。

    Attributes:
        task_id: 任务唯一标识
        image: 要拉取的镜像名称
        status: 任务状态
    """

    task_id: str
    image: str
    status: str


class PullProgressLayer(BaseModel):
    """单层拉取进度。

    Attributes:
        id: 层 ID
        status: 原始状态（如 Pulling、Pull complete）
        status_text: 中文状态描述
        current: 已下载字节数
        total: 总字节数
        progress_text: 人类可读进度（如 "15MB/30MB"）
        percentage: 该层进度百分比（0-100）
        speed: 下载速度（字节/秒），非下载中为 0
    """

    id: str
    status: str
    status_text: str
    current: int
    total: int
    progress_text: str
    percentage: int
    speed: int


class PullProgressEvent(BaseModel):
    """拉取进度事件。

    Attributes:
        total_layers: 总层数
        completed_layers: 已完成层数
        current_layer: 当前正在处理的层 ID
        percentage: 总进度百分比（0-100）
        status: 当前整体状态描述（中文）
        speed: 总体下载速度（字节/秒）
        total_size: 总大小（字节）
        downloaded_size: 已下载大小（字节）
        size_text: 人类可读总进度（如 "45MB/70MB"）
        layers: 各层进度明细
    """

    total_layers: int
    completed_layers: int
    current_layer: str
    percentage: int
    status: str
    speed: int
    total_size: int
    downloaded_size: int
    size_text: str
    layers: list[PullProgressLayer]


class PullTaskStatus(BaseModel):
    """拉取任务完整状态。

    Attributes:
        task_id: 任务唯一标识
        image: 镜像名称
        status: 任务状态（pulling/completed/failed）
        progress: 进度信息
        error: 错误信息（失败时）
        created_at: 创建时间
        updated_at: 更新时间
        completed_at: 完成时间
    """

    task_id: str
    image: str
    status: str
    progress: PullProgressEvent
    error: str | None
    created_at: str
    updated_at: str
    completed_at: str | None


class RegistryCreate(BaseModel):
    """创建镜像搜索接口配置请求。

    Attributes:
        name: 配置名称
        search_api_url: 镜像搜索 API 主地址
        mirror_url: 镜像搜索 API 镜像地址（可选，兼容旧字段）
        mirror_urls: 镜像地址列表（可选）
        enable_mirror: 是否启用镜像地址作为 fallback
        username: 认证用户名（可选）
        password: 认证密码（可选）
        trust_ssl_self_signed: 是否信任 SSL 自我签署证书
    """

    name: str
    search_api_url: str
    mirror_url: str | None = None
    mirror_urls: list[str] | None = None
    enable_mirror: bool = False
    username: str | None = None
    password: str | None = None
    trust_ssl_self_signed: bool = False


class RegistryUpdate(BaseModel):
    """更新镜像搜索接口配置请求。

    Attributes:
        name: 配置名称
        search_api_url: 镜像搜索 API 主地址
        mirror_url: 镜像搜索 API 镜像地址（可选，兼容旧字段）
        mirror_urls: 镜像地址列表（可选）
        enable_mirror: 是否启用镜像地址作为 fallback
        username: 认证用户名（可选）
        password: 认证密码（可选）
        trust_ssl_self_signed: 是否信任 SSL 自我签署证书
    """

    name: str | None = None
    search_api_url: str | None = None
    mirror_url: str | None = None
    mirror_urls: list[str] | None = None
    enable_mirror: bool | None = None
    username: str | None = None
    password: str | None = None
    trust_ssl_self_signed: bool | None = None


class RegistryOut(BaseModel):
    """镜像搜索接口配置响应。

    Attributes:
        id: 配置记录 ID
        name: 配置名称
        search_api_url: 镜像搜索 API 主地址
        mirror_url: 镜像搜索 API 镜像地址（兼容旧字段）
        mirror_urls: 镜像地址列表
        enable_mirror: 是否启用镜像地址
        username: 认证用户名
        trust_ssl_self_signed: 是否信任 SSL 自我签署证书
        is_default: 是否设为默认
        created_at: 创建时间
        updated_at: 更新时间
    """

    id: int
    name: str
    search_api_url: str
    mirror_url: str | None = None
    mirror_urls: list[str] | None = None
    enable_mirror: bool = False
    username: str | None = None
    trust_ssl_self_signed: bool = False
    is_default: bool = False
    created_at: datetime
    updated_at: datetime

    @field_validator("mirror_urls", mode="before")
    @classmethod
    def parse_mirror_urls(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat() if value else ""

    class Config:
        from_attributes = True


class BatchImageDeleteRequest(BaseModel):
    """批量删除镜像请求。

    Attributes:
        ids: 要删除的镜像 ID 列表
        force: 是否强制删除
    """

    ids: list[str]
    force: bool = False


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
