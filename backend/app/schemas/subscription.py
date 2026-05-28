"""
订阅相关的 Pydantic Schema 模块。

定义订阅模块的请求/响应数据模型：
- SubscriptionCreate: 创建订阅的请求数据
- SubscriptionResponse: 订阅信息的响应数据
"""

from datetime import datetime
from pydantic import BaseModel


class SubscriptionCreate(BaseModel):
    """
    创建订阅请求数据模型。

    用于校验创建订阅接口提交的数据。用户通过此模型指定要订阅的插件实例
    和具体的监控项。

    Attributes:
        instance_id: 要订阅的插件实例 ID
        item_id: 订阅项在插件中的唯一标识
        item_title: 订阅项的标题/名称
        item_meta: 订阅项的附加元数据，默认为空字典
    """

    instance_id: int  # 插件实例 ID
    item_id: str  # 订阅项标识
    item_title: str  # 订阅项标题
    item_meta: dict = {}  # 附加元数据，默认为空


class SubscriptionResponse(BaseModel):
    """
    订阅信息响应数据模型。

    用于序列化返回给客户端的订阅完整信息，包含订阅状态和时间等字段。

    Attributes:
        id: 订阅 ID
        user_id: 所属用户 ID
        instance_id: 关联的插件实例 ID
        item_id: 订阅项标识
        item_title: 订阅项标题
        item_meta: 订阅项元数据
        status: 订阅状态（如 "active"、"paused" 等）
        last_checked: 上次检查更新的时间，未检查过时为 None
        created_at: 订阅创建时间
    """

    id: int  # 订阅 ID
    user_id: int  # 所属用户 ID
    instance_id: int  # 插件实例 ID
    item_id: str  # 订阅项标识
    item_title: str  # 订阅项标题
    item_meta: dict  # 订阅项元数据
    status: str  # 订阅状态
    last_checked: datetime | None  # 上次检查时间，可为空
    created_at: datetime  # 创建时间

    # 允许从 ORM 模型对象直接构造（from_attributes=True）
    model_config = {"from_attributes": True}
