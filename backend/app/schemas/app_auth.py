"""应用客户端认证检测相关 Schema。"""

from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class AppAuthType(str, Enum):
    """应用认证类型。"""

    none = "none"
    basic = "basic"
    api_key = "api_key"


class AppAuthVerifyRequest(BaseModel):
    """应用认证检测请求。"""

    app_name: str = Field(..., min_length=1, description="应用名")
    url: HttpUrl = Field(..., description="应用访问地址")
    auth_type: AppAuthType = Field(default=AppAuthType.none, description="认证类型")
    username: str | None = Field(default=None, description="用户名")
    password: str | None = Field(default=None, description="密码")
    api_key: str | None = Field(default=None, description="API Key")


class AppAuthVerifyResponse(BaseModel):
    """应用认证检测响应。"""

    valid: bool = Field(..., description="是否验证通过")
    message: str | None = Field(default=None, description="检测结果描述")
