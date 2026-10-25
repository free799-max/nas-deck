"""编排模板与部署相关的 Pydantic Schema。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.orchestration.composition import AppCompositionItem


class OrchestrationOut(BaseModel):
    """应用编排列表/详情响应模型。"""

    id: int
    name: str
    display_name: str
    description: str | None
    category: str
    icon: str | None
    website: str | None
    source_url: str | None
    version: str
    # 管理端当前版本的更新说明
    changelog: str | None = None
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


class OrchestrationUpdateEventOut(BaseModel):
    """模板/实例组版本变更记录。"""

    id: int
    orchestration_name: str
    scope: str
    group_id: int | None = None
    from_version: str | None = None
    to_version: str | None = None
    mode: str
    status: str
    detail: dict = {}
    message: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
