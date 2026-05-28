"""
通知渠道相关的 Pydantic Schema 模块。

定义通知渠道模块的请求/响应数据模型：
- NotificationChannelCreate: 创建通知渠道的请求数据
- NotificationChannelResponse: 通知渠道信息的响应数据
- NotificationTestRequest: 测试通知渠道的请求数据
"""

from pydantic import BaseModel


class NotificationChannelCreate(BaseModel):
    """
    创建通知渠道请求数据模型。

    用于校验创建通知渠道接口提交的数据。

    Attributes:
        type: 渠道类型标识（如 "email"、"webhook"、"telegram" 等）
        config: 渠道配置参数，默认为空字典
        enabled: 是否启用该渠道，默认启用
    """

    type: str  # 渠道类型，如 "email"、"webhook"、"telegram"
    config: dict = {}  # 渠道配置参数，默认为空
    enabled: bool = True  # 是否启用，默认 True


class NotificationChannelResponse(BaseModel):
    """
    通知渠道信息响应数据模型。

    用于序列化返回给客户端的通知渠道完整信息。

    Attributes:
        id: 渠道 ID
        user_id: 所属用户 ID
        type: 渠道类型
        config: 渠道配置参数
        enabled: 是否启用
    """

    id: int  # 渠道 ID
    user_id: int  # 所属用户 ID
    type: str  # 渠道类型
    config: dict  # 渠道配置参数
    enabled: bool  # 是否启用

    # 允许从 ORM 模型对象直接构造（from_attributes=True）
    model_config = {"from_attributes": True}


class NotificationTestRequest(BaseModel):
    """
    测试通知渠道请求数据模型。

    用于校验发送测试通知接口提交的数据。与创建不同，测试请求不关联
    已保存的渠道，而是直接提供类型和配置用于临时测试。

    Attributes:
        type: 要测试的渠道类型
        config: 测试使用的渠道配置参数
    """

    type: str  # 测试的渠道类型
    config: dict  # 测试使用的配置参数
