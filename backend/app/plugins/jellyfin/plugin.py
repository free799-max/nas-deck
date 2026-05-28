"""
Jellyfin 媒体服务器插件。

本模块实现了与 Jellyfin 媒体服务器的集成，通过 Jellyfin 的 REST API
完成以下功能：
- 连接测试：验证服务器地址和 API Key 是否有效
- 获取数据源：拉取 Jellyfin 中的媒体库列表
- 获取数据项：拉取指定媒体库中的媒体条目（电影、剧集等）
- 检查更新：检测已订阅剧集是否有新集数上线

认证方式：使用 API Key，通过 X-Emby-Token 请求头传递。

Jellyfin API 文档参考：https://jellyfin.org/docs/general/networking/api
"""

import httpx

# 导入插件基类和数据模型
from app.plugins.base import BasePlugin, Source, Item, Update


class JellyfinPlugin(BasePlugin):
    """
    Jellyfin 媒体服务器插件类。

    通过 Jellyfin REST API 与媒体服务器交互，支持获取媒体库、
    媒体条目以及检测剧集更新。认证采用 API Key 方式，
    通过 X-Emby-Token 请求头进行身份验证。
    """

    # 插件内部标识名
    name = "jellyfin"
    # 插件显示名称
    display_name = "Jellyfin"
    # 插件版本号
    version = "1.0.0"
    # 插件描述
    description = "Jellyfin media server integration"

    # 插件配置 Schema，定义用户需要提供的配置项
    config_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "title": "Server URL"},       # Jellyfin 服务器地址
            "api_key": {"type": "string", "title": "API Key"},      # Jellyfin API 密钥
        },
        "required": ["url", "api_key"],  # url 和 api_key 为必填项
    }

    def _headers(self, config: dict) -> dict:
        """
        构建请求认证头。

        将用户配置中的 API Key 封装为 Jellyfin 要求的 X-Emby-Token 请求头。

        Args:
            config: 插件配置字典，需包含 'api_key' 字段

        Returns:
            dict: 包含认证信息的请求头字典
        """
        return {"X-Emby-Token": config["api_key"]}

    async def test_connection(self, config: dict) -> bool:
        """
        测试与 Jellyfin 服务器的连接。

        通过请求系统信息接口（/System/Info）来验证服务器地址
        和 API Key 是否有效。请求超时时间为 10 秒。

        Args:
            config: 插件配置字典，需包含 'url' 和 'api_key'

        Returns:
            bool: 连接成功（HTTP 200）返回 True，否则返回 False
        """
        try:
            async with httpx.AsyncClient() as client:
                # 请求 Jellyfin 系统信息接口验证连接
                resp = await client.get(
                    f"{config['url']}/System/Info",
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
        获取 Jellyfin 中的媒体库列表。

        请求虚拟文件夹接口（/Library/VirtualFolders）获取所有媒体库，
        每个媒体库作为一个数据源返回，包含其 ID、名称和集合类型。

        Args:
            config: 插件配置字典，需包含 'url' 和 'api_key'

        Returns:
            list[Source]: 媒体库列表，请求失败时返回空列表
        """
        try:
            async with httpx.AsyncClient() as client:
                # 请求 Jellyfin 虚拟文件夹（媒体库）列表
                resp = await client.get(
                    f"{config['url']}/Library/VirtualFolders",
                    headers=self._headers(config),
                    timeout=10,
                )
                if resp.status_code != 200:
                    return []
                # 将每个媒体库转换为 Source 对象
                return [
                    Source(
                        # 优先使用 Id，若无则使用 Name 作为标识
                        id=lib.get("Id", lib["Name"]),
                        name=lib["Name"],
                        # 保存集合类型（如 movies、tvshows 等）作为元数据
                        meta={"collection_type": lib.get("CollectionType", "")},
                    )
                    for lib in resp.json()
                ]
        except Exception:
            # 请求异常时返回空列表
            return []

    async def get_items(self, config: dict, source_id: str) -> list[Item]:
        """
        获取指定媒体库中的媒体条目列表。

        请求条目接口（/Items），按创建时间倒序排列，
        最多返回 50 个条目。每个条目包含其 ID、名称、类型、年份和简介。

        Args:
            config: 插件配置字典，需包含 'url' 和 'api_key'
            source_id: 媒体库（数据源）的唯一标识符

        Returns:
            list[Item]: 媒体条目列表，请求失败时返回空列表
        """
        try:
            async with httpx.AsyncClient() as client:
                # 请求 Jellyfin 条目列表，按创建时间倒序，限制 50 条
                resp = await client.get(
                    f"{config['url']}/Items",
                    headers=self._headers(config),
                    params={
                        "ParentId": source_id,         # 父级媒体库 ID
                        "Recursive": "true",            # 递归获取所有子条目
                        "SortBy": "DateCreated",        # 按创建时间排序
                        "SortOrder": "Descending",      # 倒序排列（最新在前）
                        "Limit": 50,                    # 最多返回 50 条
                    },
                    timeout=10,
                )
                if resp.status_code != 200:
                    return []
                # 将每个条目转换为 Item 对象
                return [
                    Item(
                        id=item["Id"],
                        title=item["Name"],
                        source_id=source_id,
                        meta={
                            "type": item.get("Type", ""),                # 媒体类型（Movie、Series 等）
                            "year": item.get("ProductionYear"),          # 制作年份
                            "overview": item.get("Overview", ""),        # 简介/剧情概述
                        },
                    )
                    for item in resp.json().get("Items", [])
                ]
        except Exception:
            # 请求异常时返回空列表
            return []

    async def check_updates(self, config: dict, subscriptions: list) -> list[Update]:
        """
        检查已订阅剧集是否有新的集数更新。

        遍历所有订阅记录，对于剧集类型（Series）的订阅，
        查询其最新一集的信息。如果存在剧集数据，则生成一条更新通知，
        包含剧集名称和最新集的季号与集号。

        Args:
            config: 插件配置字典，需包含 'url' 和 'api_key'
            subscriptions: 订阅记录列表，每条记录需包含 'id' 和 'item_id' 字段

        Returns:
            list[Update]: 更新信息列表，包含所有检测到的新集数更新
        """
        updates = []
        async with httpx.AsyncClient() as client:
            for sub in subscriptions:
                # 首先获取订阅项的详细信息，判断其类型
                resp = await client.get(
                    f"{config['url']}/Items/{sub['item_id']}",
                    headers=self._headers(config),
                    params={"Fields": "DateLastMediaAdded"},  # 请求包含最后添加媒体日期字段
                    timeout=10,
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()

                # 仅处理剧集类型（Series）的订阅
                if data.get("Type") == "Series":
                    # 请求该剧集的集数列表，按创建时间倒序，仅取最新 1 集
                    episodes_resp = await client.get(
                        f"{config['url']}/Shows/{sub['item_id']}/Episodes",
                        headers=self._headers(config),
                        params={
                            "SortBy": "DateCreated",        # 按创建时间排序
                            "SortOrder": "Descending",      # 倒序（最新在前）
                            "Limit": 1,                     # 仅获取最新 1 集
                        },
                        timeout=10,
                    )
                    if episodes_resp.status_code == 200:
                        episodes = episodes_resp.json().get("Items", [])
                        if episodes:
                            # 取最新一集的信息
                            latest = episodes[0]
                            # 生成更新通知，包含剧集名和最新集名
                            updates.append(Update(
                                subscription_id=sub["id"],
                                title=f"{data['Name']} - {latest['Name']}",
                                # 格式化显示季号和集号，如 S01E05
                                content=f"S{latest.get('ParentIndexNumber', '?')}E{latest.get('IndexNumber', '?')}",
                            ))
        return updates
