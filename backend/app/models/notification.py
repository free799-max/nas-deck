"""
通知渠道模型模块。

定义通知渠道的 ORM 模型，用于存储用户配置的各类通知推送渠道。
支持多种通知类型（如邮件、Webhook、Telegram 等），每种类型有独立的配置参数。
"""

from datetime import datetime

from sqlalchemy import String, ForeignKey, Boolean, DateTime, JSON, func
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NotificationChannel(Base):
    """
    通知渠道模型。

    用户可以创建多个通知渠道，每个渠道对应一种通知方式。
    渠道类型（type）标识通知方式，config 字段以 JSON 格式存储该渠道的配置参数。

    Attributes:
        id: 渠道唯一标识，主键自增
        user_id: 所属用户的 ID，外键关联 users 表
        type: 渠道类型标识（如 "email"、"webhook"、"telegram" 等）
        config: 渠道配置参数，JSON 格式，使用 MutableDict 支持原地修改检测
        enabled: 是否启用该渠道，默认启用
        created_at: 渠道创建时间，由数据库服务器自动生成
        user: 关联的用户对象（多对一关系）
    """

    # 数据库表名
    __tablename__ = "notification_channels"

    id: Mapped[int] = mapped_column(primary_key=True)  # 主键，自增
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))  # 外键，关联用户
    type: Mapped[str] = mapped_column(String(20))  # 渠道类型，如 "email"、"webhook" 等
    config: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)  # JSON 配置，支持原地修改追踪
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否启用，默认 True
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())  # 创建时间，数据库自动填充

    # 所属的用户，反向关联到 User.notification_channels
    user = relationship("User", back_populates="notification_channels")
