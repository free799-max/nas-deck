"""服务概览相关 Schema。"""

from pydantic import BaseModel


class OverviewAppOut(BaseModel):
    """服务概览中的单个已部署应用。"""

    id: int
    app_name: str
    display_name: str
    description: str | None = None
    icon: str | None = None
    category: str
    status: str
    # 自动生成的访问地址；无法推断时为 None
    url: str | None = None
    instance_name: str


class OverviewCategoryOut(BaseModel):
    """按分类聚合的应用分组。"""

    category: str
    apps: list[OverviewAppOut]


class AppPortOut(BaseModel):
    """容器端口映射。"""

    container_port: str
    host_ip: str | None = None
    host_port: str | None = None


class AppMetricsOut(BaseModel):
    """容器实时监控指标。"""

    cpu_percent: float = 0.0
    memory_used: int = 0
    memory_limit: int = 0
    memory_percent: float = 0.0
    network_rx: int = 0
    network_tx: int = 0
    block_read: int = 0
    block_write: int = 0
    pids: int = 0


class OverviewAppDetailOut(BaseModel):
    """应用详情：基本信息 + 容器信息 + 实时监控指标。"""

    app: OverviewAppOut
    image: str | None = None
    container_id: str | None = None
    container_name: str | None = None
    project_name: str | None = None
    restart_policy: str | None = None
    started_at: str | None = None
    uptime_seconds: int | None = None
    ports: list[AppPortOut] = []
    metrics: AppMetricsOut | None = None
    error: str | None = None


class OverviewOut(BaseModel):
    """服务概览响应。"""

    categories: list[OverviewCategoryOut]
    total: int
    running: int
