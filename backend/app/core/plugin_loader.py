"""
插件自动发现与注册模块。

提供 PluginLoader 类，用于自动扫描 app.plugins 包下的所有子模块，
发现继承自 BasePlugin 的插件类并完成实例化与注册。

本模块在导入时会创建一个全局单例 plugin_loader，供其他模块直接使用。
"""

import importlib
import pkgutil
from typing import Type

from app.plugins.base import BasePlugin


class PluginLoader:
    """插件加载器，负责插件的注册、查询与自动发现。

    插件以名称为键存储在字典中，每个插件都是 BasePlugin 子类的实例。

    Attributes:
        plugins: 插件注册表，键为插件名称（str），值为插件实例（BasePlugin）。
    """

    def __init__(self):
        """初始化插件加载器，创建空的插件注册表。"""
        self.plugins: dict[str, BasePlugin] = {}

    def register(self, plugin_cls: Type[BasePlugin]):
        """注册一个插件类。

        将插件类实例化后，以插件名称为键存入注册表。
        如果同名插件已存在，将被覆盖。

        Args:
            plugin_cls: 继承自 BasePlugin 的插件类（注意是类，非实例）。
        """
        instance = plugin_cls()
        self.plugins[instance.name] = instance

    def get(self, name: str) -> BasePlugin | None:
        """根据名称获取已注册的插件实例。

        Args:
            name: 插件名称。

        Returns:
            BasePlugin | None: 对应的插件实例，未找到时返回 None。
        """
        return self.plugins.get(name)

    def list_plugins(self) -> list[dict]:
        """列出所有已注册插件的元信息。

        Returns:
            list[dict]: 插件信息列表，每个字典包含 name、display_name、
                        version、description、config_schema 字段。
        """
        return [
            {
                "name": p.name,
                "display_name": p.display_name,
                "version": p.version,
                "description": p.description,
                "config_schema": p.config_schema,
            }
            for p in self.plugins.values()
        ]

    def discover(self, package_path: str = "app.plugins"):
        """自动发现并注册插件包中的所有插件类。

        扫描指定包路径下的所有子模块，查找继承自 BasePlugin 的类
        （排除 BasePlugin 自身），并调用 register 方法完成注册。

        Args:
            package_path: 要扫描的包路径，默认为 "app.plugins"。
        """
        try:
            package = importlib.import_module(package_path)
        except ModuleNotFoundError:
            # 插件包不存在时直接返回，不抛出异常
            return

        # 遍历包下的所有子模块
        for _, module_name, is_pkg in pkgutil.iter_modules(package.__path__):
            if module_name == "base":  # 跳过基类文件
                continue
            # 动态导入子模块
            module = importlib.import_module(f"{package_path}.{module_name}")
            # 检查模块中的所有属性，找到 BasePlugin 的子类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BasePlugin)
                    and attr is not BasePlugin  # 排除 BasePlugin 基类自身
                ):
                    self.register(attr)


# 全局单例，供其他模块直接导入使用
plugin_loader = PluginLoader()
