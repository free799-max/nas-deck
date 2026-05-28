"""
订阅与更新日志模型模块。

定义两个核心 ORM 模型：
- Subscription: 订阅模型，记录用户对某个插件实例中特定项目的订阅关系
- UpdateLog: 更新日志模型，记录订阅项检测到的更新内容

订阅是连接用户、插件实例和具体监控项的桥梁，更新日志则记录每次检测到的变化。
"""

from datetime import datetime

from sqlalchemy import String, ForeignKey, DateTime, JSON, Boolean, Text, func
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Subscription(Base):
    """
    订阅模型。

    记录用户对某个插件实例中特定项目的订阅关系。例如用户订阅某个 RSS 源、
    某个商品的价格变化等。每个订阅项关联一个用户和一个插件实例。

    Attributes:
        id: 订阅唯一标识，主键自增
        user_id: 订阅用户的 ID，外键关联 users 表
        instance_id: 插件实例 ID，外键关联 plugin_instances 表
        item_id: 订阅项在插件中的唯一标识（如 RSS 源 URL、商品 ID 等）
        item_title: 订阅项的标题/名称，便于用户识别
        item_meta: 订阅项的元数据，JSON 格式，存储额外的附加信息
        last_checked: 上次检查更新的时间，可为空表示尚未检查过
        status: 订阅状态（如 "active"、"paused" 等），默认 "active"
        created_at: 订阅创建时间，由数据库服务器自动生成
        user: 关联的用户对象（多对一关系）
        instance: 关联的插件实例对象（多对一关系）
        update_logs: 该订阅的所有更新日志（一对多关系），级联删除
    """

    # 数据库表名
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)  # 主键，自增
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))  # 外键，关联用户
    instance_id: Mapped[int] = mapped_column(ForeignKey("plugin_instances.id"))  # 外键，关联插件实例
    item_id: Mapped[str] = mapped_column(String(255))  # 订阅项在插件中的标识
    item_title: Mapped[str] = mapped_column(String(255))  # 订阅项标题
    item_meta: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)  # 元数据，JSON 格式
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 上次检查时间，可为空
    status: Mapped[str] = mapped_column(String(20), default="active")  # 订阅状态，默认活跃
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())  # 创建时间，数据库自动填充

    # 关联的用户（多对一）
    user = relationship("User", back_populates="subscriptions")
    # 关联的插件实例（多对一）
    instance = relationship("PluginInstance", back_populates="subscriptions")
    # 该订阅的所有更新日志（一对多），级联删除：删除订阅时同步删除日志
    update_logs = relationship("UpdateLog", back_populates="subscription", cascade="all, delete-orphan")


class UpdateLog(Base):
    """
    更新日志模型。

    记录订阅项检测到的更新内容。每次插件检测到订阅项有新变化时，
    会创建一条更新日志，并标记是否已通过通知渠道推送给用户。

    Attributes:
        id: 日志唯一标识，主键自增
        subscription_id: 所属订阅的 ID，外键关联 subscriptions 表
        title: 更新标题，简要描述更新内容
        content: 更新的详细内容，使用 Text 类型支持长文本
        detected_at: 更新被检测到的时间，由数据库服务器自动生成
        notified: 是否已通过通知渠道推送，默认 False
        subscription: 关联的订阅对象（多对一关系）
    """

    # 数据库表名
    __tablename__ = "update_logs"

    id: Mapped[int] = mapped_column(primary_key=True)  # 主键，自增
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id"))  # 外键，关联订阅
    title: Mapped[str] = mapped_column(String(255))  # 更新标题
    content: Mapped[str] = mapped_column(Text, default="")  # 更新详情，支持长文本
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())  # 检测时间，数据库自动填充
    notified: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否已通知，默认未通知

    # 所属的订阅（多对一）
    subscription = relationship("Subscription", back_populates="update_logs")
