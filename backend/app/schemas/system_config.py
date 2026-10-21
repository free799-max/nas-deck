"""系统全局配置相关 Pydantic Schema。"""

from typing import Optional

from pydantic import BaseModel, Field


class SystemConfigBase(BaseModel):
    """系统配置基础字段。"""

    http_proxy: Optional[str] = Field(None, max_length=500, description="HTTP 代理地址")
    https_proxy: Optional[str] = Field(None, max_length=500, description="HTTPS 代理地址")
    no_proxy: Optional[str] = Field(None, max_length=500, description="不走代理的地址列表")
    service_port_start: int = Field(
        10000, ge=1, le=65535, description="服务端口顺序分配的起始端口"
    )
    default_admin_username: str = Field(
        "admin", max_length=255, description="部署服务时自动配置的统一管理员用户名"
    )
    default_admin_password: str = Field(
        "", max_length=255, description="部署服务时自动配置的统一管理员密码（留空则每次随机）"
    )


class SystemConfigOut(SystemConfigBase):
    """系统配置响应模型。"""

    id: int


class SystemConfigUpdate(SystemConfigBase):
    """系统配置更新请求模型。"""

    pass
