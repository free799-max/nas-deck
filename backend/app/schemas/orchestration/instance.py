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


class InspectFixRequest(BaseModel):
    """检测项自动修复请求。"""

    item_ids: list[str] = []


class PluginInstallRequest(BaseModel):
    """应用插件安装请求。"""

    plugin_id: str = Field(..., min_length=1, max_length=100)
    repo_url: str | None = None


class OrchestrationBackupAppOut(BaseModel):
    """备份中的应用数据目录。"""

    app_name: str
    instance_name: str | None = None


class OrchestrationBackupOut(BaseModel):
    """可恢复的实例组备份。"""

    name: str
    instance_name: str
    orchestration_name: str | None = None
    deleted_at: str | None = None
    apps: list[OrchestrationBackupAppOut] = []


class OrchestrationRestoreRequest(BaseModel):
    """从备份恢复实例组请求。"""

    backup: str = Field(..., min_length=1, max_length=200)
    instance_name: str | None = Field(None, min_length=1, max_length=100)


class OrchestrationDeleteResponse(BaseModel):
    """删除实例组任务响应。"""

    task_id: str
