"""Docker 镜像及拉取任务相关 Pydantic Schema。"""

from pydantic import BaseModel


class ImageInfo(BaseModel):
    """本地 Docker 镜像信息（扁平化，每行对应一个 tag）。"""

    id: str  # 镜像短 ID（12 位，展示用）
    image_id: str  # 镜像完整 ID（sha256:...，删除操作使用）
    name: str  # Repository 名称（如 "nginx"）
    tag: str  # Tag（如 "latest"）
    full_tag: str  # 完整标签（如 "nginx:latest"）
    size: int  # 镜像大小（字节）
    created: str  # 创建时间（ISO 8601 格式）
    containers: int  # 使用该镜像的容器数量


class ImageLayer(BaseModel):
    """镜像层信息（用于详情弹窗表格展示）。"""

    order: int
    size: int
    layer: str


class ImageDetail(BaseModel):
    """Docker 镜像完整元数据。"""

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
    """移除未使用镜像的结果。"""

    deleted: list[str]
    space_reclaimed: int


class ImageSearchResult(BaseModel):
    """Docker Hub 镜像搜索结果。"""

    name: str
    description: str
    star_count: int
    pull_count: int
    official: bool
    is_automated: bool


class ImagePullRequest(BaseModel):
    """镜像拉取请求。"""

    image: str


class ImageTag(BaseModel):
    """镜像标签信息。"""

    name: str
    last_updated: str
    size: int
    digest: str


class PullTaskResponse(BaseModel):
    """启动拉取任务响应。"""

    task_id: str
    image: str
    status: str


class PullProgressLayer(BaseModel):
    """单层拉取进度。"""

    id: str
    status: str
    status_text: str
    current: int
    total: int
    progress_text: str
    percentage: int
    speed: int


class PullProgressEvent(BaseModel):
    """拉取进度事件。"""

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
    """拉取任务完整状态。"""

    task_id: str
    image: str
    status: str
    progress: PullProgressEvent
    error: str | None
    created_at: str
    updated_at: str
    completed_at: str | None


class BatchImageDeleteRequest(BaseModel):
    """批量删除镜像请求。"""

    ids: list[str]
    force: bool = False
