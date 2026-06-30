"""应用编排相关的 Pydantic Schema 模块。"""

from pydantic import BaseModel, ConfigDict

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
    "DeployTaskCreateResponse",
    "DeployTaskProgress",
    "DeployTaskStage",
    "DeployTaskStatus",
    "DeployTaskType",
    "OrchestrationDeployRequest",
    "OrchestrationDeployResponse",
    "OrchestrationDetailOut",
    "OrchestrationOut",
]
