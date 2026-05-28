"""
钉钉（DingTalk）Webhook 通知器模块。

本模块实现了通过钉钉自定义机器人的 Webhook 地址发送 Markdown 格式通知消息。
用户需提供 Webhook URL 作为必填配置项。
"""

import httpx

from app.core.notifiers.base import BaseNotifier


class DingTalkNotifier(BaseNotifier):
    """
    钉钉通知器。

    通过钉钉自定义机器人 Webhook 发送 Markdown 格式的通知消息。

    Attributes:
        name: 通知渠道标识，固定为 "dingtalk"。
        config_schema: 配置参数的 JSON Schema，定义了 webhook_url 必填字段。
    """

    name = "dingtalk"
    config_schema = {
        "type": "object",
        "properties": {
            "webhook_url": {"type": "string", "title": "Webhook URL"},
        },
        "required": ["webhook_url"],
    }

    async def send(self, title: str, content: str, config: dict, **kwargs) -> bool:
        """
        通过钉钉 Webhook 发送 Markdown 格式通知消息。

        消息以钉钉机器人 Markdown 消息格式发送，标题在消息列表中显示，
        正文以三级标题加内容的形式展示。

        Args:
            title: 通知消息的标题，同时用于消息列表摘要和正文三级标题。
            content: 通知消息的正文内容。
            config: 包含 webhook_url 的配置字典。
            **kwargs: 扩展参数（当前未使用）。

        Returns:
            bool: HTTP 状态码为 200 时返回 True（发送成功），请求异常或状态码非 200 返回 False。
        """
        try:
            async with httpx.AsyncClient() as client:
                # 按照钉钉机器人 Webhook 消息格式构造请求体
                resp = await client.post(config["webhook_url"], json={
                    "msgtype": "markdown",
                    "markdown": {"title": title, "text": f"### {title}\n{content}"},
                })
                # HTTP 200 表示消息发送成功
                return resp.status_code == 200
        except httpx.RequestError:
            # 网络请求异常（超时、连接失败等），返回 False
            return False
