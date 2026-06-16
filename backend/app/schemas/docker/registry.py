"""镜像搜索接口配置（Registry）相关 Pydantic Schema。"""

import json
from datetime import datetime

from pydantic import BaseModel, field_serializer, field_validator


class RegistryCreate(BaseModel):
    """创建镜像搜索接口配置请求。"""

    name: str
    search_api_url: str
    mirror_url: str | None = None
    mirror_urls: list[str] | None = None
    enable_mirror: bool = False
    username: str | None = None
    password: str | None = None
    trust_ssl_self_signed: bool = False


class RegistryUpdate(BaseModel):
    """更新镜像搜索接口配置请求。"""

    name: str | None = None
    search_api_url: str | None = None
    mirror_url: str | None = None
    mirror_urls: list[str] | None = None
    enable_mirror: bool | None = None
    username: str | None = None
    password: str | None = None
    trust_ssl_self_signed: bool | None = None


class RegistryOut(BaseModel):
    """镜像搜索接口配置响应。"""

    id: int
    name: str
    search_api_url: str
    mirror_url: str | None = None
    mirror_urls: list[str] | None = None
    enable_mirror: bool = False
    username: str | None = None
    trust_ssl_self_signed: bool = False
    is_default: bool = False
    created_at: datetime
    updated_at: datetime

    @field_validator("mirror_urls", mode="before")
    @classmethod
    def parse_mirror_urls(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat() if value else ""

    class Config:
        from_attributes = True
