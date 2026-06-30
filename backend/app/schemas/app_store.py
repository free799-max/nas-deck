"""应用商店相关的 Pydantic Schema 模块。"""

from pydantic import BaseModel, ConfigDict


class AppOut(BaseModel):
    """应用商店列表/详情响应模型。"""

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
    image: str | None
    default_ports: list[dict]
    config_schema: dict
    version: str
    is_builtin: bool
    type: str
    changelog: str | None
    backup_paths: list[str]

    model_config = ConfigDict(from_attributes=True)


class AppDetailOut(AppOut):
    """应用详情响应模型，包含 README 说明。"""

    readme: str | None

    model_config = ConfigDict(from_attributes=True)


class AppDeployRequest(BaseModel):
    """应用部署请求模型。"""

    instance_name: str
    config: dict = {}


class AppPreviewResponse(BaseModel):
    """应用 Compose YAML 预览响应模型。

    校验通过时 yaml 为渲染后的 YAML，error 为空；
    校验失败时 error 为错误描述，yaml 为空。
    """

    yaml: str | None = None
    error: str | None = None

    model_config = ConfigDict(from_attributes=True)
