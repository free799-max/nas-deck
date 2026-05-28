"""
用户模型模块。

定义系统中的用户 ORM 模型，包含用户的认证信息和关联关系。
用户是系统的核心实体，与订阅（Subscription）和通知渠道（NotificationChannel）
为一对多关系。
"""

from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """
    用户模型。

    存储用户的认证信息和基本属性。每个用户可以拥有多个订阅和多个通知渠道，
    删除用户时会级联删除其关联的订阅和通知渠道。

    Attributes:
        id: 用户唯一标识，主键自增
        username: 用户名，全局唯一，建立索引加速查询
        hashed_password: 经过哈希处理的密码，不存储明文
        role: 用户角色，默认为 "user"，可扩展为 "admin" 等
        created_at: 用户注册时间，由数据库服务器自动生成
        subscriptions: 该用户的所有订阅（一对多关系）
        notification_channels: 该用户的所有通知渠道（一对多关系）
    """

    # 数据库表名
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)  # 主键，自增
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)  # 用户名，唯一且有索引
    hashed_password: Mapped[str] = mapped_column(String(255))  # 哈希后的密码
    role: Mapped[str] = mapped_column(String(20), default="user")  # 用户角色，默认普通用户
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())  # 创建时间，数据库自动填充

    # 该用户的所有订阅，级联删除：删除用户时同步删除其所有订阅
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    # 该用户的所有通知渠道，级联删除：删除用户时同步删除其所有通知渠道
    notification_channels = relationship("NotificationChannel", back_populates="user", cascade="all, delete-orphan")
