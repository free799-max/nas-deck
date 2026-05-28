"""
插件实例相关的 Pydantic Schema 模块。

定义插件实例模块的请求/响应数据模型：
- PluginInstanceCreate: 创建插件实例的请求数据
- PluginInstanceResponse: 插件实例信息的响应数据
- PluginInfo: 插件元信息（来自插件包自身的描述信息）
"""

from pydantic import BaseModel


class PluginInstanceCreate(BaseModel):
    """
    创建插件实例请求数据模型。

    用于校验创建插件实例接口提交的数据。

    Attributes:
        plugin_name: 插件标识名称（对应插件包名）
        display_name: 用户可见的显示名称
        config: 插件配置参数，默认为空字典
    """

    plugin_name: str  # 插件标识名
    display_name: str  # 显示名称
    config: dict = {}  # 插件配置，默认为空


class PluginInstanceResponse(BaseModel):
    """
    插件实例信息响应数据模型。

    用于序列化返回给客户端的插件实例完整信息。

    Attributes:
        id: 实例 ID
        plugin_name: 插件标识名称
        display_name: 显示名称
        config: 插件配置参数
        docker_id: 关联的 Docker 容器 ID，未绑定时为 None
        enabled: 是否启用
    """

    id: int  # 实例 ID
    plugin_name: str  # 插件标识名
    display_name: str  # 显示名称
    config: dict  # 插件配置参数
    docker_id: str | None  # Docker 容器 ID，可为空
    enabled: bool  # 是否启用

    # 允许从 ORM 模型对象直接构造（from_attributes=True）
    model_config = {"from_attributes": True}


class PluginInfo(BaseModel):
    """
    插件元信息数据模型。

    描述插件包自身的元数据，由插件开发者定义，用于展示插件详情
    和配置表单。不涉及数据库存储，仅作为传输模型使用。

    Attributes:
        name: 插件标识名称
        display_name: 插件显示名称
        version: 插件版本号
        description: 插件功能描述
        config_schema: 插件配置的 JSON Schema，定义配置项的结构和验证规则
    """

    name: str  # 插件标识名
    display_name: str  # 显示名称
    version: str  # 版本号
    description: str  # 功能描述
    config_schema: dict  # 配置项的 JSON Schema
