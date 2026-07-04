"""应用客户端注册表。

通过 ``register_client`` 注册各应用客户端，后续即可按应用名统一获取。
"""

from app.core.exceptions import APIException
from app.services.apps.base import AppClient

_CLIENTS: dict[str, type[AppClient]] = {}


def register_client(name: str, client_cls: type[AppClient]) -> None:
    """注册应用客户端类。"""
    _CLIENTS[name] = client_cls


def get_client(name: str) -> type[AppClient]:
    """按应用名获取客户端类，未注册时抛出 APIException。"""
    client_cls = _CLIENTS.get(name)
    if client_cls is None:
        raise APIException(f"应用 {name} 暂无客户端支持", 400)
    return client_cls


def list_supported_clients() -> list[str]:
    """返回已注册的应用名列表。"""
    return list(_CLIENTS.keys())
