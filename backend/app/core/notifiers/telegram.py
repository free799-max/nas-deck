"""
Telegram Bot API 通知器模块。

本模块实现了通过 Telegram Bot API 的 sendMessage 接口发送 Markdown 格式通知消息。
用户需提供 Bot Token 和 Chat ID 两个必填配置项。
"""

import httpx

from app.core.notifiers.base import BaseNotifier


class TelegramNotifier(BaseNotifier):
    """
    Telegram 通知器。

    通过 Telegram Bot API 向指定聊天发送 Markdown 格式的通知消息。

    Attributes:
        name: 通知渠道标识，固定为 "telegram"。
        config_schema: 配置参数的 JSON Schema，定义了 bot_token 和 chat_id 两个必填字段。
    """

    name = "telegram"
    config_schema = {
        "type": "object",
        "properties": {
            "bot_token": {"type": "string", "title": "Bot Token"},
            "chat_id": {"type": "string", "title": "Chat ID"},
        },
        "required": ["bot_token", "chat_id"],
    }

    async def send(self, title: str, content: str, config: dict, **kwargs) -> bool:
        """
        通过 Telegram Bot API 发送通知消息。

        将标题以加粗格式、正文以普通格式拼接后，通过 sendMessage 接口发送到指定聊天。

        Args:
            title: 通知消息的标题，发送时以 Markdown 加粗格式显示。
            content: 通知消息的正文内容。
            config: 包含 bot_token 和 chat_id 的配置字典。
            **kwargs: 扩展参数（当前未使用）。

        Returns:
            bool: HTTP 状态码为 200 时返回 True（发送成功），请求异常或状态码非 200 返回 False。
        """
        # 拼接 Telegram Bot API 的 sendMessage 请求地址
        url = f"https://api.telegram.org/bot{config['bot_token']}/sendMessage"
        try:
            async with httpx.AsyncClient() as client:
                # 发送 Markdown 格式的消息，标题加粗显示
                resp = await client.post(url, json={
                    "chat_id": config["chat_id"],
                    "text": f"*{title}*\n{content}",
                    "parse_mode": "Markdown",
                })
                # HTTP 200 表示消息发送成功
                return resp.status_code == 200
        except httpx.RequestError:
            # 网络请求异常（超时、连接失败等），返回 False
            return False
