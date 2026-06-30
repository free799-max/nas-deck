"""应用编排与编排实例 ORM 模型。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AppOrchestration(Base):
    """自动化分类组合模板模型。

    定义某个自动化分类（如影视、漫画、书籍）下可一键部署的应用组合方案，
    由多个应用商店 App 组成，支持必选、可选、互斥等关系定义。
    """

    __tablename__ = "app_orchestrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    icon: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 官方网站链接
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 开源社区/源码仓库链接
    source_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    # 组合定义：该编排由哪些应用商店 App 组成
    # 示例：
    # [
    #   {"app_name": "moviepilot", "relation": "required"},
    #   {"app_name": "qbittorrent", "relation": "required"},
    #   {"app_name": "jellyfin", "relation": "optional", "group": "player"},
    #   {"app_name": "emby", "relation": "optional", "group": "player"},
    # ]
    app_composition: Mapped[list[dict]] = mapped_column(JSON, default=list)
    # 共享配置 Schema：用于让用户一次性配置跨应用的公共变量
    shared_config_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    instances: Mapped[list["AppInstance"]] = relationship(
        "AppInstance",
        back_populates="orchestration",
        cascade="all, delete-orphan",
    )
    deployment_groups: Mapped[list["AppOrchestrationInstance"]] = relationship(
        "AppOrchestrationInstance",
        back_populates="orchestration",
        cascade="all, delete-orphan",
    )


class AppOrchestrationInstance(Base):
    """一次组合部署记录，关联多个 AppInstance。"""

    __tablename__ = "app_orchestration_instances"

    id: Mapped[int] = mapped_column(primary_key=True)
    orchestration_id: Mapped[int] = mapped_column(
        ForeignKey("app_orchestrations.id"), nullable=False
    )
    instance_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 组合部署时由用户填写的共享配置
    shared_config: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    # 实例运行状态：running / stopped / error / deploying
    status: Mapped[str] = mapped_column(String(20), default="deploying")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    orchestration: Mapped["AppOrchestration"] = relationship(
        "AppOrchestration", back_populates="deployment_groups"
    )
    instances: Mapped[list["AppInstance"]] = relationship(
        "AppInstance", back_populates="orchestration_group"
    )


class AppInstance(Base):
    """应用实例模型。

    记录用户基于某个 AppOrchestration 或 App 创建的一次部署，
    一对一关联到 DockerComposeProject。
    """

    __tablename__ = "app_instances"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 基于编排部署时填充
    orchestration_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_orchestrations.id"), nullable=True
    )
    # 基于应用商店应用部署时填充
    app_id: Mapped[int | None] = mapped_column(
        ForeignKey("apps.id"), nullable=True
    )
    # 组合部署时填充，标识属于同一次组合部署
    orchestration_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_orchestration_instances.id"), nullable=True
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("docker_compose_projects.id"), nullable=True, unique=True
    )
    instance_name: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    # 实例当前部署的版本
    orchestration_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    # 实例运行状态：running / stopped / error / upgrading / deploying
    status: Mapped[str] = mapped_column(String(20), default="running")
    # 实例级备份配置，可覆盖编排默认配置
    backup_config: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    last_backup_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    orchestration: Mapped["AppOrchestration | None"] = relationship(
        "AppOrchestration", back_populates="instances"
    )
    orchestration_group: Mapped["AppOrchestrationInstance | None"] = relationship(
        "AppOrchestrationInstance", back_populates="instances"
    )
    app: Mapped["App | None"] = relationship(
        "App", back_populates="instances"
    )
    project: Mapped["DockerComposeProject"] = relationship(
        "DockerComposeProject"
    )
    backups: Mapped[list["AppInstanceBackup"]] = relationship(
        "AppInstanceBackup",
        back_populates="instance",
        cascade="all, delete-orphan",
        order_by="AppInstanceBackup.created_at.desc()",
    )


class AppInstanceBackup(Base):
    """应用实例备份记录模型。

    记录每次手动或自动备份的元数据，归档文件保存在文件系统中。
    """

    __tablename__ = "app_instance_backups"

    id: Mapped[int] = mapped_column(primary_key=True)
    instance_id: Mapped[int] = mapped_column(
        ForeignKey("app_instances.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # 备份归档文件绝对路径
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    # 归档文件大小（字节）
    size: Mapped[int] = mapped_column(Integer, default=0)
    # 备份类型：manual 手动 / auto 自动 / pre_upgrade 升级前自动备份
    backup_type: Mapped[str] = mapped_column(String(20), default="manual")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    instance: Mapped["AppInstance"] = relationship(
        "AppInstance", back_populates="backups"
    )
