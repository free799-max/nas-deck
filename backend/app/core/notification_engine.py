"""
通知引擎模块。

管理所有通知渠道的注册表，提供统一的消息发送接口。
支持动态注册不同类型的通知器（如邮件、Webhook、Telegram 等），
并通过统一的 send 方法根据通知器名称分发消息。

本模块在导入时会创建一个全局单例 notification_engine，供其他模块直接使用。
"""

from typing import Type

from app.core.notifiers.base import BaseNotifier


class NotificationEngine:
    """通知引擎，管理通知器注册表并提供统一的消息发送能力。

    所有通知器必须继承自 BaseNotifier，并在初始化时提供唯一的 name 属性。
    引擎以通知器名称为键维护注册表，支持按名称查找和调用。

    Attributes:
        notifiers: 通知器注册表，键为通知器名称（str），值为通知器实例（BaseNotifier）。
    """

    def __init__(self):
        """初始化通知引擎，创建空的通知器注册表。"""
        self.notifiers: dict[str, BaseNotifier] = {}

    def register(self, notifier_cls: Type[BaseNotifier]):
        """注册一个通知器类。

        将通知器类实例化后，以通知器名称为键存入注册表。
        如果同名通知器已存在，将被覆盖。

        Args:
            notifier_cls: 继承自 BaseNotifier 的通知器类（注意是类，非实例）。
        """
        instance = notifier_cls()
        self.notifiers[instance.name] = instance

    def get(self, name: str) -> BaseNotifier | None:
        """根据名称获取已注册的通知器实例。

        Args:
            name: 通知器名称，如 "email"、"webhook" 等。

        Returns:
            BaseNotifier | None: 对应的通知器实例，未找到时返回 None。
        """
        return self.notifiers.get(name)

    def list_notifiers(self) -> list[dict]:
        """列出所有已注册通知器的元信息。

        Returns:
            list[dict]: 通知器信息列表，每个字典包含 name 和 config_schema 字段。
        """
        return [
            {"name": n.name, "config_schema": n.config_schema}
            for n in self.notifiers.values()
        ]

    async def send(self, notifier_name: str, title: str, content: str, config: dict) -> bool:
        """通过指定通知渠道发送消息。

        根据通知器名称查找对应的通知器，并调用其 send 方法发送消息。
        这是异步方法，因为底层通知操作（如 HTTP 请求）通常是 IO 密集型的。

        Args:
            notifier_name: 通知器名称，需与注册时的 name 属性一致。
            title: 通知标题。
            content: 通知正文内容。
            config: 通知渠道的配置信息，如 API Key、URL 等。

        Returns:
            bool: 发送成功返回 True，通知器不存在时返回 False。
        """
        notifier = self.get(notifier_name)
        if not notifier:
            # 未找到对应的通知器，返回 False 表示发送失败
            return False
        return await notifier.send(title, content, config=config)


# 全局单例，供其他模块直接导入使用
notification_engine = NotificationEngine()
