"""
插件实例模型模块。

定义系统中插件实例的 ORM 模型，用于管理已安装的插件实例及其配置。
"""

from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, JSON, func
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PluginInstance(Base):
    """
    插件实例模型。

    每个插件实例代表一个已安装和配置好的插件。实例存储插件名称、显示名称、
    配置参数等。

    Attributes:
        id: 实例唯一标识，主键自增
        plugin_name: 插件标识名称（对应插件包名），建有索引加速查询
        display_name: 用户可见的显示名称
        config: 插件配置参数，JSON 格式，使用 MutableDict 支持原地修改检测
        enabled: 是否启用该插件实例，默认启用
        created_at: 实例创建时间，由数据库服务器自动生成
    """

    # 数据库表名
    __tablename__ = "plugin_instances"

    id: Mapped[int] = mapped_column(primary_key=True)  # 主键，自增
    plugin_name: Mapped[str] = mapped_column(String(50), index=True)  # 插件标识名，有索引
    display_name: Mapped[str] = mapped_column(String(100))  # 显示名称
    config: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)  # JSON 配置，支持原地修改追踪
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否启用，默认 True
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())  # 创建时间，数据库自动填充
