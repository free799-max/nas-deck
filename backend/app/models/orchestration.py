"""应用编排与编排实例 ORM 模型。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AppOrchestration(Base):
    """应用编排模型。

    定义系统内置或管理员上传的可一键部署组合应用方案，
    包含元数据、配置 Schema、YAML 模板和 README。
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
    # 支持的架构列表，如 ["amd64", "arm64"]
    architectures: Mapped[list[str]] = mapped_column(JSON, default=list)
    readme: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    yaml_template: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    # 编排类型：compose 多容器 / container 单容器
    type: Mapped[str] = mapped_column(String(20), default="compose")
    # 版本变更日志
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 默认需要备份的路径列表（相对于宿主机或容器内）
    backup_paths: Mapped[list[str]] = mapped_column(JSON, default=list)
    # 编排源码目录，便于定位图标、README 等资源
    source_dir: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 部署后推荐用户创建的插件名称列表
    suggested_plugins: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    instances: Mapped[list["AppInstance"]] = relationship(
        "AppInstance",
        back_populates="orchestration",
        cascade="all, delete-orphan",
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
    project_id: Mapped[int] = mapped_column(
        ForeignKey("docker_compose_projects.id"), nullable=False, unique=True
    )
    instance_name: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    # 实例当前部署的版本
    orchestration_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    # 实例运行状态：running / stopped / error / upgrading
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
