"""
插件实例模型模块。

定义插件实例的 ORM 模型，用于管理系统中已安装的插件实例。
每个插件实例对应一个具体的插件配置，可以选择性地绑定一个 Docker 容器。
插件实例是订阅的上游实体，用户通过订阅插件实例来追踪信息更新。
"""

from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, JSON, func
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PluginInstance(Base):
    """
    插件实例模型。

    每个插件实例代表一个已安装和配置好的插件。实例存储插件名称、显示名称、
    配置参数等。一个插件实例可以关联一个 Docker 容器（用于隔离运行），
    也可以被多个用户订阅。

    Attributes:
        id: 实例唯一标识，主键自增
        plugin_name: 插件标识名称（对应插件包名），建有索引加速查询
        display_name: 用户可见的显示名称
        config: 插件配置参数，JSON 格式，使用 MutableDict 支持原地修改检测
        docker_id: 关联的 Docker 容器 ID，可为空表示未绑定容器
        enabled: 是否启用该插件实例，默认启用
        created_at: 实例创建时间，由数据库服务器自动生成
        subscriptions: 该实例的所有订阅（一对多关系）
        container: 关联的 Docker 容器对象（一对一关系，uselist=False）
    """

    # 数据库表名
    __tablename__ = "plugin_instances"

    id: Mapped[int] = mapped_column(primary_key=True)  # 主键，自增
    plugin_name: Mapped[str] = mapped_column(String(50), index=True)  # 插件标识名，有索引
    display_name: Mapped[str] = mapped_column(String(100))  # 显示名称
    config: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)  # JSON 配置，支持原地修改追踪
    docker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Docker 容器 ID，可为空
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否启用，默认 True
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())  # 创建时间，数据库自动填充

    # 该插件实例的所有订阅（一对多）
    subscriptions = relationship("Subscription", back_populates="instance")
    # 关联的 Docker 容器（一对一，uselist=False）
    container = relationship("DockerContainer", back_populates="instance", uselist=False)
