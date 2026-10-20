"""系统全局配置模型。

用于存储 NasDeck 的全局设置，如代理、存储目录等。
整个系统只使用一条记录（id=1）来保存配置。
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SystemConfig(Base):
    """系统全局配置模型。

    Attributes:
        id: 配置记录唯一标识，固定为 1
        http_proxy: HTTP 代理地址
        https_proxy: HTTPS 代理地址
        no_proxy: 不走代理的地址列表
        storage_host_root_dir: 存储宿主机根目录
        storage_docker_mount_dir: 存储 Docker 容器挂载目录
        service_port_start: 服务端口顺序分配的起始端口
        default_admin_username: 部署服务时自动配置的统一管理员用户名
        default_admin_password: 部署服务时自动配置的统一管理员密码（空则每次随机）
        created_at: 记录创建时间
        updated_at: 记录最后更新时间
    """

    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    http_proxy: Mapped[str | None] = mapped_column(String(500), nullable=True)
    https_proxy: Mapped[str | None] = mapped_column(String(500), nullable=True)
    no_proxy: Mapped[str | None] = mapped_column(String(500), nullable=True)
    storage_host_root_dir: Mapped[str | None] = mapped_column(String(500), nullable=True)
    storage_docker_mount_dir: Mapped[str | None] = mapped_column(String(500), nullable=True)
    service_port_start: Mapped[int] = mapped_column(
        Integer, default=10000, server_default="10000", nullable=False
    )
    default_admin_username: Mapped[str] = mapped_column(
        String(255), default="admin", server_default="admin", nullable=False
    )
    default_admin_password: Mapped[str] = mapped_column(
        String(255), default="", server_default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )
