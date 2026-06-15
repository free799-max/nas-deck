"""Docker 容器模型模块。

定义 Docker 容器的 ORM 模型，用于跟踪插件实例对应的 Docker 容器状态。
每个插件实例最多关联一个 Docker 容器（一对一关系）。
"""

from datetime import datetime

from sqlalchemy import String, Text, ForeignKey, DateTime, func, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


COMPOSE_PROJECT_LABEL = "nasdeck.compose.project"
"""Compose 项目标签键，用于标识容器归属。"""


class DockerMirrorConfig(Base):
    """Docker 镜像搜索接口配置模型。

    支持配置多条镜像搜索接口，其中一条可设为默认使用。
    当主地址不可用且启用了镜像地址时，自动 fallback 到镜像地址。

    Attributes:
        id: 配置记录唯一标识，主键自增
        name: 配置名称（如 "Docker Hub 官方"）
        search_api_url: 镜像搜索 API 主地址
        mirror_url: 镜像搜索 API 镜像地址（可选）
        enable_mirror: 是否启用镜像地址作为 fallback
        username: 认证用户名（可选）
        password: 认证密码（可选）
        is_default: 是否设为当前默认使用的配置
        created_at: 创建时间
        updated_at: 更新时间
    """

    __tablename__ = "docker_mirror_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    search_api_url: Mapped[str] = mapped_column(String(500), nullable=False)
    mirror_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mirror_urls: Mapped[str | None] = mapped_column(Text, nullable=True)
    enable_mirror: Mapped[bool] = mapped_column(default=False)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trust_ssl_self_signed: Mapped[bool] = mapped_column(default=False)
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )


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


class DockerComposeProject(Base):
    """Docker Compose 项目模型。

    记录 Compose 项目的元数据、当前激活版本与运行时配置文件路径。
    支持系统创建的项目与从 Docker 自动发现的外部项目统一维护。

    Attributes:
        id: 项目唯一标识
        project_name: CLI 项目名（唯一，用于 docker compose -p）
        description: 项目描述
        is_active: 是否启用
        config_files: compose 文件路径列表（JSON 序列化）
        working_dir: compose 执行工作目录
        created_at: 创建时间
        updated_at: 更新时间
        versions: 关联的版本列表
        stack: 关联的运行时状态（一对一）
    """

    __tablename__ = "docker_compose_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    config_files: Mapped[str | None] = mapped_column(Text, nullable=True)
    working_dir: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list["DockerComposeVersion"]] = relationship(
        "DockerComposeVersion",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="DockerComposeVersion.version_number.desc()",
    )
    stack: Mapped["DockerComposeStack | None"] = relationship(
        "DockerComposeStack",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )


class DockerComposeVersion(Base):
    """Docker Compose 版本模型。

    保存每个 Compose 项目的历史 YAML 版本内容。

    Attributes:
        id: 版本唯一标识
        project_id: 所属项目 ID
        version_number: 版本号（自动递增）
        content: YAML 内容
        comment: 版本说明
        created_by_user_id: 创建用户 ID
        created_at: 创建时间
        project: 关联的项目
    """

    __tablename__ = "docker_compose_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("docker_compose_projects.id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    project: Mapped["DockerComposeProject"] = relationship(
        "DockerComposeProject", back_populates="versions"
    )


class DockerComposeStack(Base):
    """Docker Compose Stack 运行时状态缓存。

    记录项目的实时状态摘要，避免每次查询都调用 CLI。

    Attributes:
        id: 状态记录唯一标识
        project_id: 所属项目 ID
        status: Stack 整体状态
        service_count: 服务总数
        running_count: 运行中服务数
        ports: 端口映射摘要（JSON）
        last_action: 最后执行的操作
        last_action_at: 最后操作时间
        updated_at: 更新时间
        project: 关联的项目
    """

    __tablename__ = "docker_compose_stacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("docker_compose_projects.id"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    service_count: Mapped[int] = mapped_column(Integer, default=0)
    running_count: Mapped[int] = mapped_column(Integer, default=0)
    ports: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_action: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_action_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    project: Mapped["DockerComposeProject"] = relationship(
        "DockerComposeProject", back_populates="stack"
    )
