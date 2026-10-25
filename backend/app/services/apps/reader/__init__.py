"""Reader 自动同步与账号配置所需的接口封装。"""

from app.services.apps.reader.app_client import ReaderAppClient
from app.services.apps.reader.client import (
    ErmaoClient,
    ErmaoClientError,
    ReaderClientError,
    ReaderSession,
)
from app.services.apps.reader.epub import (
    EpubFixResult,
    clean_markup,
    epub_failures,
    fix_epub,
)

__all__ = [
    "ErmaoClient",
    "ErmaoClientError",
    "EpubFixResult",
    "ReaderAppClient",
    "ReaderClientError",
    "ReaderSession",
    "clean_markup",
    "epub_failures",
    "fix_epub",
]
