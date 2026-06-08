"""
插件抽象基类与数据模型模块。

本模块定义了插件系统的核心抽象接口和通用数据结构：
- Source: 数据源（如媒体库、书库等）的数据模型
- Item: 数据项（如电影、剧集、漫画系列等）的数据模型
- BasePlugin: 插件抽象基类，所有插件必须继承此类并实现其抽象方法

所有具体插件（Jellyfin、Komga、MoviePilot 等）均基于此模块的接口进行开发。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Source:
    """
    数据源数据类。

    表示一个可订阅的数据源，例如 Jellyfin 中的媒体库、
    Komga 中的书库等。每个数据源都有唯一的标识和显示名称。

    Attributes:
        id: 数据源的唯一标识符，由插件生成
        name: 数据源的显示名称，用于前端展示
        meta: 附加元数据字典，存储数据源的额外信息（如类型、描述等），
              默认为空字典
    """
    id: str
    name: str
    meta: dict = field(default_factory=dict)


@dataclass
class Item:
    """
    数据项数据类。

    表示数据源中的一个具体条目，例如一部电影、一个剧集、
    一个漫画系列等。数据项是用户订阅的基本单位。

    Attributes:
        id: 数据项的唯一标识符，由插件从外部服务获取
        title: 数据项的标题，用于前端展示
        source_id: 所属数据源的 ID，用于关联数据源
        meta: 附加元数据字典，存储数据项的额外信息（如年份、类型、简介等），
              默认为空字典
    """
    id: str
    title: str
    source_id: str
    meta: dict = field(default_factory=dict)


class BasePlugin(ABC):
    """
    插件抽象基类。

    所有插件必须继承此类并实现其定义的抽象方法。
    每个插件对应一个外部媒体服务的集成，负责与该服务的 API 交互。

    子类必须定义以下类属性：
        name: 插件的内部标识名（小写，用于程序内部引用）
        display_name: 插件的显示名称（用于前端展示）
        version: 插件版本号
        description: 插件的简短描述
        config_schema: 插件配置的 JSON Schema 定义，用于验证和生成配置表单

    抽象方法：
        test_connection: 测试与外部服务的连接是否正常
        get_sources: 获取外部服务中可用的数据源列表
        get_items: 获取指定数据源中的数据项列表
    """
    # 插件内部标识名（小写字母）
    name: str
    # 插件显示名称（用于前端展示）
    display_name: str
    # 插件版本号
    version: str
    # 插件简短描述
    description: str
    # 插件配置的 JSON Schema，用于验证用户输入的配置参数
    config_schema: dict

    @abstractmethod
    async def test_connection(self, config: dict) -> bool:
        """
        测试与外部服务的连接是否正常。

        使用用户提供的配置信息尝试连接外部服务，
        验证认证凭据和服务可达性。

        Args:
            config: 插件配置字典，包含连接所需的信息（如 URL、API Key 等）

        Returns:
            bool: 连接成功返回 True，失败返回 False
        """
        ...

    @abstractmethod
    async def get_sources(self, config: dict) -> list[Source]:
        """
        获取外部服务中可用的数据源列表。

        从外部服务拉取所有可供用户订阅的数据源，
        例如媒体库列表、书库列表等。

        Args:
            config: 插件配置字典，包含连接所需的信息

        Returns:
            list[Source]: 数据源列表，连接失败时返回空列表
        """
        ...

    @abstractmethod
    async def get_items(self, config: dict, source_id: str) -> list[Item]:
        """
        获取指定数据源中的数据项列表。

        根据给定的数据源 ID，从外部服务拉取该数据源下的所有可订阅条目，
        例如某个媒体库中的电影列表、某个书库中的系列列表等。

        Args:
            config: 插件配置字典，包含连接所需的信息
            source_id: 数据源的唯一标识符

        Returns:
            list[Item]: 数据项列表，连接失败时返回空列表
        """
        ...
