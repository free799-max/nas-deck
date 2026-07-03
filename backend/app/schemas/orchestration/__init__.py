"""应用编排相关的 Pydantic Schema 模块。"""

from typing import Literal

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.orchestration.deploy_task import (
    ComposeDeployResponse,
    DeployTaskCreateResponse,
    DeployTaskProgress,
    DeployTaskStage,
    DeployTaskStatus,
    DeployTaskType,
)


class AppCompositionItem(BaseModel):
    """组合中的应用定义。"""

    app_name: str
    relation: str  # required / optional / suggested / conflicting
    group: str | None = None
    conflict_with: list[str] = []


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


class OrchestrationInstanceAppOut(BaseModel):
    """编排实例组中的应用实例概要。"""

    id: int
    app_name: str
    display_name: str
    icon: str | None = None
    status: str
    config: dict = {}


class OrchestrationInstanceGroupOut(BaseModel):
    """编排实例组（一次部署/导入记录）概要。"""

    id: int
    instance_name: str
    orchestration_name: str
    orchestration_display_name: str
    status: str
    created_at: datetime
    apps: list[OrchestrationInstanceAppOut] = []

    model_config = ConfigDict(from_attributes=True)


class OrchestrationInstanceDetailOut(OrchestrationInstanceGroupOut):
    """编排实例组详情，包含可编辑的配置信息。"""

    shared_config: dict = {}
    app_configs: dict = {}


class OrchestrationInstanceUpdateRequest(BaseModel):
    """编排实例组更新请求。"""

    instance_name: str | None = Field(None, min_length=1, max_length=100)
    shared_config: dict | None = None
    app_configs: dict | None = None


class OrchestrationOut(BaseModel):
    """应用编排列表/详情响应模型。"""

    id: int
    name: str
    display_name: str
    description: str | None
    category: str
    tags: list[str]
    icon: str | None
    website: str | None
    source_url: str | None
    version: str
    is_builtin: bool
    app_composition: list[AppCompositionItem]
    shared_config_schema: dict

    model_config = ConfigDict(from_attributes=True)


class OrchestrationDetailOut(OrchestrationOut):
    """应用编排详情响应模型。"""

    model_config = ConfigDict(from_attributes=True)


class OrchestrationDeployRequest(BaseModel):
    """组合部署请求模型。"""

    instance_name: str
    selected_apps: list[str]
    app_configs: dict[str, dict] = {}
    shared_config: dict = {}


class OrchestrationDeployResponse(BaseModel):
    """组合部署响应模型。"""

    group_id: int
    instance_name: str
    status: str
    task_ids: list[str]


__all__ = [
    "AppCompositionItem",
    "ComposeDeployResponse",
    "ContainerMatch",
    "DeployTaskCreateResponse",
    "DeployTaskProgress",
    "DeployTaskStage",
    "DeployTaskStatus",
    "DeployTaskType",
    "ImportCandidateApp",
    "OrchestrationDeployRequest",
    "OrchestrationDeployResponse",
    "OrchestrationDetailOut",
    "OrchestrationImportAppConfig",
    "OrchestrationImportRequest",
    "OrchestrationImportResponse",
    "OrchestrationInstanceAppOut",
    "OrchestrationInstanceDetailOut",
    "OrchestrationInstanceGroupOut",
    "OrchestrationInstanceUpdateRequest",
    "OrchestrationOut",
]
