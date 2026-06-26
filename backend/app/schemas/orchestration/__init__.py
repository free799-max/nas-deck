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
    architectures: list[str]
    config_schema: dict
    version: str
    is_builtin: bool
    type: str
    changelog: str | None
    backup_paths: list[str]
    source_dir: str | None

    model_config = ConfigDict(from_attributes=True)


class OrchestrationDetailOut(OrchestrationOut):
    """应用编排详情响应模型，包含完整 README。"""

    readme: str | None
    suggested_plugins: list[str] = []

    model_config = ConfigDict(from_attributes=True)


class OrchestrationDeployRequest(BaseModel):
    """一键部署编排请求模型。"""

    instance_name: str
    config: dict = {}


class OrchestrationDeployResponse(BaseModel):
    """一键部署编排响应模型。"""

    instance_id: int
    project_id: int
    project_name: str
    instance_name: str
    status: str
    pending_config: dict = {}


__all__ = [
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
