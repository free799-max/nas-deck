"""部署任务相关的 Pydantic Schema 模块。"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DeployTaskType(str, Enum):
    """部署任务类型。"""

    APP_DEPLOY = "app_deploy"
    COMPOSE_DEPLOY = "compose_deploy"
    COMPOSE_ACTION = "compose_action"


class DeployTaskStage(str, Enum):
    """部署任务阶段。"""

    PREPARING = "preparing"
    CREATING_PROJECT = "creating_project"
    WRITING_COMPOSE = "writing_compose"
    PULLING_IMAGES = "pulling_images"
    STARTING_SERVICES = "starting_services"
    SYNCING_STATUS = "syncing_status"
    COMPLETED = "completed"
    FAILED = "failed"


class DeployTaskProgress(BaseModel):
    """部署任务进度详情。"""

    percentage: int = Field(0, ge=0, le=100)
    stage: str = DeployTaskStage.PREPARING
    message: str = "准备中"
    detail: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DeployTaskCreateResponse(BaseModel):
    """启动部署任务后的响应。"""

    task_id: str
    instance_id: int | None = None
    project_id: int | None = None
    status: str = "deploying"

    model_config = ConfigDict(from_attributes=True)


class DeployTaskStatus(BaseModel):
    """部署任务状态查询响应。"""

    task_id: str
    type: str
    status: str
    stage: str
    progress: DeployTaskProgress
    error: str | None = None
    instance_id: int | None = None
    project_id: int | None = None
    action: str | None = None
    created_at: str
    updated_at: str
    completed_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ComposeDeployResponse(BaseModel):
    """Compose 部署/操作任务响应。"""

    task_id: str
    project_id: int
    action: str
    status: str = "deploying"

    model_config = ConfigDict(from_attributes=True)
