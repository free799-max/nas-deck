"""编排组合与导入相关的 Pydantic Schema。"""

from typing import Literal

from pydantic import BaseModel, Field


class AppCompositionItem(BaseModel):
    """组合中的应用定义。"""

    app_name: str
    relation: str  # required / optional / suggested / conflicting
    group: str | None = None
    conflict_with: list[str] = []
    # 部署后自动装配声明，如 [{"type": "downloader", "from": "qbittorrent"}]
    integrations: list[dict] | None = None


class ContainerMatch(BaseModel):
    """扫描到的单个容器匹配信息。"""

    container_id: str
    container_name: str
    image: str
    network_ip: str | None = None
    host_port: int | None = None
    container_port: str | None = None
    suggested_url: str | None = None


class ImportCandidateApp(BaseModel):
    """某个应用在当前 Docker 环境中的导入候选信息。"""

    app_name: str
    display_name: str
    icon: str | None = None
    relation: str
    group: str | None = None
    matched: bool
    candidates: list[ContainerMatch] = []


class OrchestrationImportAppConfig(BaseModel):
    """导入时为单个应用填写的访问与认证配置。"""

    selected_container_id: str | None = None
    auth_type: Literal["none", "basic", "api_key"] | None = "none"
    url: str | None = None
    username: str | None = None
    password: str | None = None
    api_key: str | None = None


class OrchestrationImportRequest(BaseModel):
    """组合导入请求模型。"""

    instance_name: str = Field(..., min_length=1, max_length=100)
    selected_apps: list[str] = []
    app_configs: dict[str, OrchestrationImportAppConfig] = {}
    shared_config: dict = {}


class OrchestrationImportResponse(BaseModel):
    """组合导入响应模型。"""

    group_id: int
    instance_name: str
    status: str
    created_app_instance_ids: list[int]
