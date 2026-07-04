"""应用客户端抽象基类与通用模型。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AuthVerifyResult:
    """应用认证检测结果。"""

    valid: bool
    message: str | None = None


class AppClientError(Exception):
    """应用客户端内部异常。"""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class AppClient(ABC):
    """应用专属客户端抽象基类。

    每个受支持的应用都应实现一个子类，并注册到 registry 中。
    子类除 ``verify_auth`` 外，还可以按需扩展站点、订阅、下载等接口。
    """

    name: str

    @abstractmethod
    async def verify_auth(self, config: dict) -> AuthVerifyResult:
        """校验应用访问地址与认证信息是否有效。"""
        ...
