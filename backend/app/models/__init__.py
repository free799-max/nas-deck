"""
模型包初始化模块。

集中导出所有 SQLAlchemy ORM 模型类，方便其他模块通过
`from app.models import User, Subscription` 的方式直接引用，
而无需关心模型定义在哪个子模块中。

导出的模型：
- User: 用户模型
- PluginInstance: 插件实例模型
- Subscription: 订阅模型
- UpdateLog: 更新日志模型
- NotificationChannel: 通知渠道模型
- DockerContainer: Docker 容器模型
"""

from app.models.user import User
from app.models.plugin import PluginInstance
from app.models.subscription import Subscription, UpdateLog
from app.models.notification import NotificationChannel
from app.models.docker import DockerContainer

# __all__ 显式声明公开导出的模型名称，便于 `from app.models import *` 使用
__all__ = [
    "User", "PluginInstance", "Subscription", "UpdateLog",
    "NotificationChannel", "DockerContainer",
]
