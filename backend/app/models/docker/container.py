"""Docker 容器与镜像 Registry 配置 ORM 模型。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DockerMirrorConfig(Base):
    """Docker 镜像搜索接口配置模型。

    支持配置多条镜像搜索接口，其中一条可设为默认使用。
    """

    __tablename__ = "docker_mirror_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    search_api_url: Mapped[str] = mapped_column(String(500), nullable=False)
    mirror_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mirror_urls: Mapped[str | None] = mapped_column(Text, nullable=True)
    enable_mirror: Mapped[bool] = mapped_column(Boolean, default=False)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trust_ssl_self_signed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )
