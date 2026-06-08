"""
MoviePilot 媒体自动化插件。

本模块实现了与 MoviePilot 媒体自动化工具的集成，通过 MoviePilot 的 REST API
完成以下功能：
- 连接测试：验证服务器地址和 API Key 是否有效
- 获取数据源：返回预定义的订阅和下载中两个数据源
- 获取数据项：拉取 MoviePilot 中的订阅列表

认证方式：使用 Bearer Token，通过 Authorization 请求头传递 API Key。

MoviePilot 项目地址：https://github.com/jxxghp/MoviePilot
"""

import httpx

# 导入插件基类和数据模型
from app.plugins.base import BasePlugin, Source, Item


class MoviePilotPlugin(BasePlugin):
    """
    MoviePilot 媒体自动化插件类。

    通过 MoviePilot REST API 与媒体自动化服务交互，支持获取订阅列表
    以及检测下载历史。认证采用 Bearer Token 方式，
    通过 Authorization 请求头传递 API Key。
    """

    # 插件内部标识名
    name = "moviepilot"
    # 插件显示名称
    display_name = "MoviePilot"
    # 插件版本号
    version = "1.0.0"
    # 插件描述
    description = "MoviePilot media automation integration"

    # 插件配置 Schema，定义用户需要提供的配置项
    config_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "title": "Server URL"},       # MoviePilot 服务器地址
            "api_key": {"type": "string", "title": "API Key"},      # MoviePilot API 密钥
        },
        "required": ["url", "api_key"],  # url 和 api_key 为必填项
    }

    def _headers(self, config: dict) -> dict:
        """
        构建请求认证头。

        将用户配置中的 API Key 封装为 Bearer Token 格式的 Authorization 请求头。

        Args:
            config: 插件配置字典，需包含 'api_key' 字段

        Returns:
            dict: 包含 Bearer Token 认证信息的请求头字典
        """
        return {"Authorization": f"Bearer {config['api_key']}"}

    async def test_connection(self, config: dict) -> bool:
        """
        测试与 MoviePilot 服务器的连接。

        通过请求系统状态接口（/api/v1/system/status）来验证服务器地址
        和 API Key 是否有效。请求超时时间为 10 秒。

        Args:
            config: 插件配置字典，需包含 'url' 和 'api_key'

        Returns:
            bool: 连接成功（HTTP 200）返回 True，否则返回 False
        """
        try:
            async with httpx.AsyncClient() as client:
                # 请求 MoviePilot 系统状态接口验证连接
                resp = await client.get(
                    f"{config['url']}/api/v1/system/status",
                    headers=self._headers(config),
                    timeout=10,
                )
                # 状态码为 200 表示连接成功
                return resp.status_code == 200
        except Exception:
            # 网络异常或连接超时等情况，返回 False
            return False

    async def get_sources(self, config: dict) -> list[Source]:
        """
        获取 MoviePilot 中的数据源列表。

        返回预定义的两个数据源：
        - subscribes: 订阅列表，包含用户在 MoviePilot 中的所有媒体订阅
        - downloading: 下载中列表（当前未实现 get_items 查询）

        注意：此处数据源为固定定义，不需要从服务器拉取。

        Args:
            config: 插件配置字典（本方法未使用，但保持接口一致性）

        Returns:
            list[Source]: 包含 subscribes 和 downloading 两个数据源的列表
        """
        return [
            Source(id="subscribes", name="Subscribes", meta={"type": "subscribes"}),
            Source(id="downloading", name="Downloading", meta={"type": "downloading"}),
        ]

    async def get_items(self, config: dict, source_id: str) -> list[Item]:
        """
        获取指定数据源中的数据项列表。

        当前仅支持 subscribes 数据源，请求订阅列表接口（/api/v1/subscribe）
        获取用户的所有媒体订阅。每个订阅项包含其 ID、名称、类型和年份。

        Args:
            config: 插件配置字典，需包含 'url' 和 'api_key'
            source_id: 数据源标识符（目前仅支持 "subscribes"）

        Returns:
            list[Item]: 订阅项列表，请求失败或不支持的数据源返回空列表
        """
        try:
            async with httpx.AsyncClient() as client:
                # 目前仅处理 subscribes 数据源
                if source_id == "subscribes":
                    # 请求 MoviePilot 订阅列表接口
                    resp = await client.get(
                        f"{config['url']}/api/v1/subscribe",
                        headers=self._headers(config),
                        timeout=10,
                    )
                    if resp.status_code != 200:
                        return []
                    # 将每个订阅转换为 Item 对象
                    return [
                        Item(
                            id=str(s["id"]),
                            title=s.get("name", "Unknown"),      # 订阅名称
                            source_id=source_id,
                            meta={
                                "type": s.get("type", ""),        # 媒体类型（电影/电视剧等）
                                "year": s.get("year"),            # 年份
                            },
                        )
                        for s in resp.json()
                    ]
        except Exception:
            # 请求异常时静默忽略
            pass
        return []

