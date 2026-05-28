"""
用户相关的 Pydantic Schema 模块。

定义用户模块的请求/响应数据模型，用于 API 接口的参数校验和序列化：
- UserCreate: 用户注册时的请求数据
- UserLogin: 用户登录时的请求数据
- UserResponse: 用户信息的响应数据
- TokenResponse: JWT 令牌的响应数据
"""

from pydantic import BaseModel


class UserCreate(BaseModel):
    """
    用户注册请求数据模型。

    用于校验用户注册接口提交的数据。

    Attributes:
        username: 注册用户名
        password: 注册密码（明文，在服务端进行哈希处理）
    """

    username: str  # 注册用户名
    password: str  # 注册密码（明文传入，服务端哈希存储）


class UserLogin(BaseModel):
    """
    用户登录请求数据模型。

    用于校验用户登录接口提交的数据。

    Attributes:
        username: 登录用户名
        password: 登录密码（明文，与服务端哈希值比对）
    """

    username: str  # 登录用户名
    password: str  # 登录密码（明文传入）


class UserResponse(BaseModel):
    """
    用户信息响应数据模型。

    用于序列化返回给客户端的用户信息，不包含敏感字段（如密码）。

    Attributes:
        id: 用户 ID
        username: 用户名
        role: 用户角色
    """

    id: int  # 用户 ID
    username: str  # 用户名
    role: str  # 用户角色

    # 允许从 ORM 模型对象直接构造（from_attributes=True）
    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """
    JWT 令牌响应数据模型。

    登录成功后返回的访问令牌信息。

    Attributes:
        access_token: JWT 访问令牌字符串
        token_type: 令牌类型，固定为 "bearer"
    """

    access_token: str  # JWT 访问令牌
    token_type: str = "bearer"  # 令牌类型，默认 Bearer
