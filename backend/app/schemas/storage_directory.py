"""数据目录相关 Pydantic Schema。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StorageDirectoryCreate(BaseModel):
    """数据目录创建请求模型。"""

    name: str = Field(..., min_length=1, max_length=100, description="目录名称（唯一）")
    host_path: str = Field(
        ..., min_length=1, max_length=500, description="宿主机路径（compose bind source）"
    )
    mount_path: str = Field(
        ..., min_length=1, max_length=500, description="容器内路径（后端容器视角）"
    )
    remark: Optional[str] = Field(None, max_length=500, description="备注")
    enabled: bool = Field(True, description="是否启用")
    is_app_data: bool = Field(False, description="是否为应用数据目录（全局至多一条）")
    sort_order: int = Field(0, description="排序权重（越小越靠前）")


class StorageDirectoryUpdate(BaseModel):
    """数据目录更新请求模型（全字段可选）。"""

    name: Optional[str] = Field(None, min_length=1, max_length=100, description="目录名称")
    host_path: Optional[str] = Field(None, min_length=1, max_length=500, description="宿主机路径")
    mount_path: Optional[str] = Field(None, min_length=1, max_length=500, description="容器内路径")
    remark: Optional[str] = Field(None, max_length=500, description="备注")
    enabled: Optional[bool] = Field(None, description="是否启用")
    is_app_data: Optional[bool] = Field(None, description="是否为应用数据目录（全局至多一条）")
    sort_order: Optional[int] = Field(None, description="排序权重")


class StorageDirectoryOut(BaseModel):
    """数据目录响应模型。

    visible 为计算字段：mount_path 在后端容器内可见（已挂载进 backend 容器）时为 True。
    """

    id: int
    name: str
    host_path: str
    mount_path: str
    remark: Optional[str] = None
    enabled: bool
    is_app_data: bool
    sort_order: int
    visible: bool
    created_at: datetime
    updated_at: datetime
