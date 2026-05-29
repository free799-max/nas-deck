"""统一 API 响应模型。"""

from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel

T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    """统一 API 响应包装器。

    所有后端接口的成功响应和错误响应都使用此格式，
    前端通过 Axios 拦截器自动解包。

    Attributes:
        success: 请求是否成功
        data: 业务数据，错误时为 null
        message: 提示信息，成功时默认 "ok"
    """

    success: bool
    data: Optional[T] = None
    message: str = "ok"

    @classmethod
    def ok(cls, data: T = None, message: str = "ok") -> "StandardResponse[T]":
        """构造成功响应。"""
        return cls(success=True, data=data, message=message)

    @classmethod
    def fail(cls, message: str) -> "StandardResponse[Any]":
        """构造错误响应。"""
        return cls(success=False, data=None, message=message)
