"""应用专属客户端包。"""

from app.services.apps.base import AppClient, AppClientError, AuthVerifyResult
from app.services.apps.registry import get_client, list_supported_clients, register_client

# 自动注册已实现的应用客户端
from app.services.apps.jellyfin import JellyfinClient
from app.services.apps.moviepilot import MoviePilotClient
from app.services.apps.qbittorrent import QBittorrentClient

__all__ = [
    "AppClient",
    "AppClientError",
    "AuthVerifyResult",
    "get_client",
    "list_supported_clients",
    "JellyfinClient",
    "MoviePilotClient",
    "QBittorrentClient",
    "register_client",
]
