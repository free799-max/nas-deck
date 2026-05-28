"""
Docker 容器模型模块。

定义 Docker 容器的 ORM 模型，用于跟踪插件实例对应的 Docker 容器状态。
每个插件实例最多关联一个 Docker 容器（一对一关系）。
"""

from datetime import datetime

from sqlalchemy import String, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DockerContainer(Base):
    """
    Docker 容器模型。

    记录与插件实例绑定的 Docker 容器信息，包括容器 ID、名称、运行状态和健康检查结果。
    通过 instance_id 与 PluginInstance 建立一对一关系。

    Attributes:
        id: 容器记录唯一标识，主键自增
        instance_id: 关联的插件实例 ID，外键，唯一约束确保一对一关系
        container_id: Docker 引擎中的容器 ID（哈希字符串）
        name: 容器名称
        status: 容器运行状态（如 running、stopped 等），默认 "unknown"
        health: 容器健康检查状态（如 healthy、unhealthy 等），默认 "unknown"
        last_checked: 上次检查容器状态的时间，可为空
        instance: 关联的插件实例对象（反向一对一关系）
    """

    # 数据库表名
    __tablename__ = "docker_containers"

    id: Mapped[int] = mapped_column(primary_key=True)  # 主键，自增
    instance_id: Mapped[int] = mapped_column(ForeignKey("plugin_instances.id"), unique=True)  # 外键关联插件实例，唯一约束
    container_id: Mapped[str] = mapped_column(String(100))  # Docker 容器 ID
    name: Mapped[str] = mapped_column(String(100))  # 容器名称
    status: Mapped[str] = mapped_column(String(20), default="unknown")  # 运行状态，默认未知
    health: Mapped[str] = mapped_column(String(20), default="unknown")  # 健康状态，默认未知
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 上次检查时间，允许为空

    # 关联的插件实例，uselist=False 表示一对一关系
    instance = relationship("PluginInstance", back_populates="container")
