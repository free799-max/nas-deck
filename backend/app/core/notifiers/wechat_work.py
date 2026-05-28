"""
企业微信（WeChat Work）Webhook 通知器模块。

本模块实现了通过企业微信群机器人的 Webhook 地址发送 Markdown 格式通知消息。
用户需提供 Webhook URL 作为必填配置项。
"""

import httpx

from app.core.notifiers.base import BaseNotifier


class WeChatWorkNotifier(BaseNotifier):
    """
    企业微信通知器。

    通过企业微信群机器人 Webhook 发送 Markdown 格式的通知消息。

    Attributes:
        name: 通知渠道标识，固定为 "wechat_work"。
        config_schema: 配置参数的 JSON Schema，定义了 webhook_url 必填字段。
    """

    name = "wechat_work"
    config_schema = {
        "type": "object",
        "properties": {
            "webhook_url": {"type": "string", "title": "Webhook URL"},
        },
        "required": ["webhook_url"],
    }

    async def send(self, title: str, content: str, config: dict, **kwargs) -> bool:
        """
        通过企业微信 Webhook 发送 Markdown 格式通知消息。

        消息以企业微信群机器人 Markdown 消息格式发送，
        使用 content 字段承载标题和正文的完整 Markdown 内容。

        注意：企业微信的 Markdown 消息格式与钉钉略有不同，使用 "content" 字段
        而非钉钉的 "title" + "text" 双字段结构。

        Args:
            title: 通知消息的标题，以三级标题格式嵌入 content 中。
            content: 通知消息的正文内容。
            config: 包含 webhook_url 的配置字典。
            **kwargs: 扩展参数（当前未使用）。

        Returns:
            bool: HTTP 状态码为 200 时返回 True（发送成功），请求异常或状态码非 200 返回 False。
        """
        try:
            async with httpx.AsyncClient() as client:
                # 按照企业微信机器人 Webhook 消息格式构造请求体
                resp = await client.post(config["webhook_url"], json={
                    "msgtype": "markdown",
                    "markdown": {"content": f"### {title}\n{content}"},
                })
                # HTTP 200 表示消息发送成功
                return resp.status_code == 200
        except httpx.RequestError:
            # 网络请求异常（超时、连接失败等），返回 False
            return False
