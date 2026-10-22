"""应用专属客户端包。"""

from app.services.apps.base import (
    AppClient,
    AppClientError,
    AuthVerifyResult,
    FixResultItem,
    InspectItem,
    InspectReport,
    LogsReader,
    ProvisionResult,
)
from app.services.apps.registry import get_client, list_supported_clients, register_client

# 自动注册已实现的应用客户端
from app.services.apps.comic_auto import ComicAutoClient
from app.services.apps.jellyfin import JellyfinClient
from app.services.apps.kavita import KavitaClient
from app.services.apps.komga import KomgaClient
from app.services.apps.moviepilot import MoviePilotClient
from app.services.apps.qbittorrent import QBittorrentClient

__all__ = [
    "AppClient",
    "AppClientError",
    "AuthVerifyResult",
    "FixResultItem",
    "InspectItem",
    "InspectReport",
    "LogsReader",
    "ProvisionResult",
    "get_client",
    "list_supported_clients",
    "ComicAutoClient",
    "JellyfinClient",
    "KavitaClient",
    "KomgaClient",
    "MoviePilotClient",
    "QBittorrentClient",
    "register_client",
]
