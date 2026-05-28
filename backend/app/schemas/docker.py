"""
Docker 容器相关的 Pydantic Schema 模块。

定义容器管理模块的请求/响应数据模型：
- ContainerInfo: 容器信息的响应数据
- ContainerAction: 容器操作的请求数据
"""

from typing import Literal

from pydantic import BaseModel


class ContainerInfo(BaseModel):
    """
    容器信息响应数据模型。

    用于序列化返回给客户端的 Docker 容器基本信息。

    Attributes:
        id: 容器 ID（Docker 引擎中的哈希字符串）
        name: 容器名称
        status: 容器运行状态（如 running、exited 等）
        health: 容器健康检查状态（如 healthy、unhealthy 等）
        image: 容器所使用的镜像名称
    """

    id: str  # 容器 ID
    name: str  # 容器名称
    status: str  # 运行状态
    health: str  # 健康检查状态
    image: str  # 使用的镜像名称


class ContainerAction(BaseModel):
    """
    容器操作请求数据模型。

    用于校验容器控制接口的请求参数，只允许 start、stop、restart 三种操作。

    Attributes:
        action: 要执行的操作，限定为 "start"、"stop" 或 "restart"
    """

    action: Literal["start", "stop", "restart"]  # 操作类型，限定三种取值
