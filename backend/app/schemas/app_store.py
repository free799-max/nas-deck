"""应用商店相关的 Pydantic Schema 模块。"""

from pydantic import BaseModel, ConfigDict, Field


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
    """应用详情响应模型，包含 README 说明与 Compose YAML 模板。"""

    readme: str | None
    yaml_template: str | None

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


class AppCreate(BaseModel):
    """创建应用商店应用请求模型。"""

    name: str = Field(..., min_length=1, max_length=50)
    display_name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    category: str = Field(default="other", max_length=50)
    tags: list[str] = Field(default_factory=list)
    icon: str | None = Field(default=None, max_length=255)
    website: str | None = Field(default=None, max_length=255)
    source_url: str | None = Field(default=None, max_length=255)
    architectures: list[str] = Field(default_factory=lambda: ["amd64", "arm64"])
    image: str | None = Field(default=None, max_length=255)
    default_ports: list[dict] = Field(default_factory=list)
    config_schema: dict = Field(default_factory=dict)
    yaml_template: str = Field(..., min_length=1)
    readme: str | None = None
    version: str = Field(default="1.0.0", max_length=20)
    type: str = Field(default="compose", max_length=20)
    changelog: str | None = None
    backup_paths: list[str] = Field(default_factory=list)


class AppUpdate(BaseModel):
    """更新应用商店应用请求模型，所有字段可选（name 不可修改）。"""

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    category: str | None = Field(default=None, max_length=50)
    tags: list[str] | None = None
    icon: str | None = Field(default=None, max_length=255)
    website: str | None = Field(default=None, max_length=255)
    source_url: str | None = Field(default=None, max_length=255)
    architectures: list[str] | None = None
    image: str | None = Field(default=None, max_length=255)
    default_ports: list[dict] | None = None
    config_schema: dict | None = None
    yaml_template: str | None = Field(default=None, min_length=1)
    readme: str | None = None
    version: str | None = Field(default=None, max_length=20)
    type: str | None = Field(default=None, max_length=20)
    changelog: str | None = None
    backup_paths: list[str] | None = None


class AppTemplatePreviewRequest(BaseModel):
    """未落库应用模板预览请求模型（创建/编辑页实时预览用）。"""

    yaml_template: str = Field(..., min_length=1)
    config_schema: dict = Field(default_factory=dict)
    image: str | None = None
    app_name: str = Field(default="preview-app", max_length=50)
