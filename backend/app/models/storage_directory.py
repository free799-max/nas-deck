"""数据目录模型。

数据目录是供大数据量应用使用的可挂载目录，每个目录记录宿主机路径
（compose bind source）与容器内路径（后端容器视角/表单填写视角）的对应关系。
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StorageDirectory(Base):
    """数据目录模型。

    Attributes:
        id: 记录唯一标识
        name: 目录名称（唯一）
        host_path: 宿主机路径，应用 compose 文件 bind source 使用该路径
        mount_path: 容器内路径，后端容器视角（表单填写/目录浏览使用该路径）
        remark: 备注
        enabled: 是否启用
        is_app_data: 是否为应用数据目录（全局至多一条，存放应用自身持久化小数据）
        sort_order: 排序权重（越小越靠前）
        created_at: 记录创建时间
        updated_at: 记录最后更新时间
    """

    __tablename__ = "storage_directories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    host_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mount_path: Mapped[str] = mapped_column(String(500), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )
    is_app_data: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )
