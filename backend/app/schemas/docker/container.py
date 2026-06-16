"""Docker 容器相关 Pydantic Schema。"""

from typing import Literal

from pydantic import BaseModel


class PortMapping(BaseModel):
    """容器端口映射配置。"""

    container: str  # 容器端口，如 "80/tcp"
    host: str  # 宿主机端口，如 "8080" 或 "127.0.0.1:8080"


class EnvVar(BaseModel):
    """环境变量键值对。"""

    key: str
    value: str


class VolumeMount(BaseModel):
    """卷挂载配置。"""

    host: str  # 宿主机路径
    container: str  # 容器内路径
    mode: Literal["rw", "ro"] = "rw"  # 读写模式


class LabelItem(BaseModel):
    """标签键值对。"""

    key: str
    value: str


class ContainerInfo(BaseModel):
    """
    容器信息响应数据模型。

    用于序列化返回给客户端的 Docker 容器基本信息。
    """

    id: str  # 容器 ID
    name: str  # 容器名称
    status: str  # 运行状态
    state: str  # 状态摘要
    health: str  # 健康检查状态
    image: str  # 使用的镜像
    ports: str  # 端口映射摘要
    labels: dict[str, str]  # 容器标签
    created: str  # 创建时间


class ContainerAction(BaseModel):
    """
    容器操作请求数据模型。

    用于校验容器控制接口的请求参数，只允许 start、stop、restart 三种操作。
    """

    action: Literal["start", "stop", "restart"]  # 操作类型


class ContainerActionResponse(BaseModel):
    """容器操作响应数据模型。"""

    status: str
    error: str = ""


class ContainerCreateRequest(BaseModel):
    """创建容器请求数据模型。"""

    image: str
    name: str | None = None
    command: str | None = None
    entrypoint: str | None = None
    ports: list[PortMapping] | None = None
    environment: list[EnvVar] | None = None
    volumes: list[VolumeMount] | None = None
    network: str | None = None
    labels: list[LabelItem] | None = None
    restart_policy: Literal["no", "unless-stopped", "always", "on-failure"] = "no"
    auto_start: bool = True


class ContainerPortBinding(BaseModel):
    """容器端口绑定详情。"""

    container_port: str
    host_ip: str
    host_port: str


class ContainerMount(BaseModel):
    """容器挂载详情。"""

    type: str
    source: str
    destination: str
    mode: str
    rw: bool


class ContainerNetwork(BaseModel):
    """容器网络信息。"""

    name: str
    ip_address: str
    gateway: str
    mac_address: str


class ContainerDetail(BaseModel):
    """容器详情响应数据模型。"""

    id: str
    name: str
    image: str
    status: str
    state: str
    health: str
    command: list[str] | None = None
    entrypoint: list[str] | None = None
    env: list[str] | None = None
    working_dir: str | None = None
    user: str | None = None
    labels: dict[str, str] | None = None
    ports: list[ContainerPortBinding]
    mounts: list[ContainerMount]
    networks: list[ContainerNetwork]
    restart_policy: str
    network_mode: str
    privileged: bool
    created: str
    started_at: str
    finished_at: str
    exit_code: int
    error: str


class ContainerBatchActionRequest(BaseModel):
    """批量容器操作请求数据模型。"""

    ids: list[str]
    action: Literal["start", "stop", "restart", "remove"]


class ContainerExecRequest(BaseModel):
    """容器内执行命令请求数据模型。"""

    command: str
    workdir: str | None = None
    user: str | None = None
    environment: list[EnvVar] | None = None


class ContainerExecResponse(BaseModel):
    """容器内执行命令响应数据模型。"""

    exit_code: int
    output: str
