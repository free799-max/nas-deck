"""
通知器抽象基类模块。

本模块定义了所有通知渠道（如 Telegram、钉钉、企业微信等）的统一抽象接口。
所有具体的通知器实现都必须继承 BaseNotifier 并实现 send 方法。
"""

from abc import ABC, abstractmethod


class BaseNotifier(ABC):
    """
    通知器抽象基类。

    所有通知渠道的具体实现都应继承此类，并提供 name 属性、config_schema 配置 schema
    以及 send 方法的具体实现。

    Attributes:
        name: 通知渠道的唯一标识名称，例如 "telegram"、"dingtalk"、"wechat_work"。
        config_schema: 通知渠道所需的配置参数 JSON Schema，用于校验用户填写的配置。
    """

    name: str
    config_schema: dict

    @abstractmethod
    async def send(self, title: str, content: str, config: dict, **kwargs) -> bool:
        """
        发送通知消息（抽象方法，子类必须实现）。

        Args:
            title: 通知消息的标题。
            content: 通知消息的正文内容。
            config: 通知渠道的配置字典，包含该渠道所需的认证信息（如 token、webhook_url 等）。
            **kwargs: 预留的扩展参数，供子类在需要时使用。

        Returns:
            bool: 发送成功返回 True，发送失败返回 False。
        """
        ...

    async def test(self, config: dict) -> bool:
        """
        测试通知渠道是否连通。

        通过发送一条预设的测试消息来验证用户提供的配置是否正确可用。

        Args:
            config: 通知渠道的配置字典。

        Returns:
            bool: 测试消息发送成功返回 True，失败返回 False。
        """
        return await self.send("NasDeck Test", "Notification channel connected!", config)
