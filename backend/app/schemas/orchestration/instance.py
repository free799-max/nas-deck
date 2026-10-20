"""编排实例组相关的 Pydantic Schema。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
