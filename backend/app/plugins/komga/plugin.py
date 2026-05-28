"""
Komga 漫画服务器插件。

本模块实现了与 Komga 漫画/漫画服务器的集成，通过 Komga 的 REST API
完成以下功能：
- 连接测试：验证服务器地址和用户名/密码是否有效
- 获取数据源：拉取 Komga 中的书库列表
- 获取数据项：拉取指定书库中的漫画系列列表
- 检查更新：检测已订阅系列是否有新书发布

认证方式：使用 HTTP Basic Auth，通过用户名和密码进行身份验证。

Komga API 文档参考：https://komga.org/guides/rest.html
"""

import httpx

# 导入插件基类和数据模型
from app.plugins.base import BasePlugin, Source, Item, Update


class KomgaPlugin(BasePlugin):
    """
    Komga 漫画服务器插件类。

    通过 Komga REST API 与漫画服务器交互，支持获取书库、
    漫画系列以及检测系列更新。认证采用 HTTP Basic Auth 方式，
    使用用户名和密码进行身份验证。
    """

    # 插件内部标识名
    name = "komga"
    # 插件显示名称
    display_name = "Komga"
    # 插件版本号
    version = "1.0.0"
    # 插件描述
    description = "Komga comic/manga server integration"

    # 插件配置 Schema，定义用户需要提供的配置项
    config_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "title": "Server URL"},           # Komga 服务器地址
            "username": {"type": "string", "title": "Username"},        # 登录用户名
            "password": {"type": "string", "title": "Password"},        # 登录密码
        },
        "required": ["url", "username", "password"],  # url、username、password 均为必填项
    }

    def _auth(self, config: dict) -> tuple[str, str]:
        """
        构建认证信息元组。

        将用户配置中的用户名和密码封装为 httpx 要求的认证元组格式，
        用于 HTTP Basic Auth 认证。

        Args:
            config: 插件配置字典，需包含 'username' 和 'password' 字段

        Returns:
            tuple[str, str]: (用户名, 密码) 格式的认证元组
        """
        return (config["username"], config["password"])

    async def test_connection(self, config: dict) -> bool:
        """
        测试与 Komga 服务器的连接。

        通过请求书库列表接口（/api/v1/libraries）来验证服务器地址
        和用户名/密码是否有效。请求超时时间为 10 秒。

        Args:
            config: 插件配置字典，需包含 'url'、'username' 和 'password'

        Returns:
            bool: 连接成功（HTTP 200）返回 True，否则返回 False
        """
        try:
            async with httpx.AsyncClient() as client:
                # 请求 Komga 书库列表接口验证连接和认证
                resp = await client.get(
                    f"{config['url']}/api/v1/libraries",
                    auth=self._auth(config),
                    timeout=10,
                )
                # 状态码为 200 表示连接和认证均成功
                return resp.status_code == 200
        except Exception:
            # 网络异常或连接超时等情况，返回 False
            return False

    async def get_sources(self, config: dict) -> list[Source]:
        """
        获取 Komga 中的书库列表。

        请求书库列表接口（/api/v1/libraries）获取所有书库，
        每个书库作为一个数据源返回。

        Args:
            config: 插件配置字典，需包含 'url'、'username' 和 'password'

        Returns:
            list[Source]: 书库列表，请求失败时返回空列表
        """
        try:
            async with httpx.AsyncClient() as client:
                # 请求 Komga 书库列表
                resp = await client.get(
                    f"{config['url']}/api/v1/libraries",
                    auth=self._auth(config),
                    timeout=10,
                )
                if resp.status_code != 200:
                    return []
                # 将每个书库转换为 Source 对象
                return [
                    Source(id=lib["id"], name=lib["name"])
                    for lib in resp.json()
                ]
        except Exception:
            # 请求异常时返回空列表
            return []

    async def get_items(self, config: dict, source_id: str) -> list[Item]:
        """
        获取指定书库中的漫画系列列表。

        请求系列列表接口（/api/v1/series），按最后修改时间倒序排列，
        最多返回 50 个系列。每个系列包含其 ID、标题和书籍数量。

        Args:
            config: 插件配置字典，需包含 'url'、'username' 和 'password'
            source_id: 书库（数据源）的唯一标识符

        Returns:
            list[Item]: 漫画系列列表，请求失败时返回空列表
        """
        try:
            async with httpx.AsyncClient() as client:
                # 请求 Komga 系列列表，按最后修改时间倒序，限制 50 条
                resp = await client.get(
                    f"{config['url']}/api/v1/series",
                    auth=self._auth(config),
                    params={
                        "library_id": source_id,               # 按书库 ID 过滤
                        "size": 50,                            # 每页数量限制
                        "sort": "lastModified,desc",           # 按最后修改时间倒序
                    },
                    timeout=10,
                )
                if resp.status_code != 200:
                    return []
                # 将每个系列转换为 Item 对象
                return [
                    Item(
                        id=s["id"],
                        title=s["metadata"]["title"],         # 系列标题
                        source_id=source_id,
                        # 保存书籍总数作为元数据
                        meta={"books_count": s.get("booksCount", 0)},
                    )
                    for s in resp.json().get("content", [])    # Komga 返回分页格式，内容在 content 字段中
                ]
        except Exception:
            # 请求异常时返回空列表
            return []

    async def check_updates(self, config: dict, subscriptions: list) -> list[Update]:
        """
        检查已订阅系列是否有新书发布。

        遍历所有订阅记录，查询每个订阅系列的最新一本书的信息。
        如果存在书籍数据，则生成一条更新通知，包含书名和编号。

        Args:
            config: 插件配置字典，需包含 'url'、'username' 和 'password'
            subscriptions: 订阅记录列表，每条记录需包含 'id' 和 'item_id' 字段

        Returns:
            list[Update]: 更新信息列表，包含所有检测到的新书更新
        """
        updates = []
        try:
            async with httpx.AsyncClient() as client:
                for sub in subscriptions:
                    # 请求该系列下的书籍列表，按编号倒序，仅取最新 1 本
                    resp = await client.get(
                        f"{config['url']}/api/v1/series/{sub['item_id']}/books",
                        auth=self._auth(config),
                        params={
                            "sort": "number,desc",  # 按编号倒序排列
                            "size": 1,              # 仅获取最新 1 本
                        },
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        books = resp.json().get("content", [])
                        if books:
                            # 取最新一本书的信息
                            latest = books[0]
                            # 生成更新通知，包含书名和编号
                            updates.append(Update(
                                subscription_id=sub["id"],
                                title=f"New book: {latest['metadata']['title']}",
                                # 显示书籍编号（如第几卷/期）
                                content=f"Number: {latest.get('number', '?')}",
                            ))
        except Exception:
            # 发生异常时静默忽略，返回已收集到的更新
            pass
        return updates
