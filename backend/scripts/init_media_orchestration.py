"""初始化影视自动化组合模板数据。"""

import sys
from pathlib import Path

# 将项目根目录加入路径，支持从 scripts/ 子目录运行
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models.orchestration import AppOrchestration


MEDIA_COMPOSITION = [
    {"app_name": "moviepilot", "relation": "required"},
    {"app_name": "qbittorrent", "relation": "required"},
    {"app_name": "jellyfin", "relation": "optional", "group": "player"},
    {"app_name": "emby", "relation": "optional", "group": "player"},
]

MEDIA_SHARED_CONFIG_SCHEMA = {
    "properties": {
        "media_root": {
            "type": "string",
            "title": "媒体库根目录",
            "description": "所有媒体应用共享的媒体库根目录",
            "format": "directory",
            "default": "media",
        },
        "downloads_root": {
            "type": "string",
            "title": "下载根目录",
            "description": "下载工具保存资源的根目录",
            "format": "directory",
            "default": "downloads",
        },
    },
}


async def main():
    async with async_session() as db:
        result = await db.execute(
            select(AppOrchestration).where(AppOrchestration.name == "media-stack")
        )
        orch = result.scalar_one_or_none()
        if orch is None:
            print("media-stack not found")
            return

        orch.display_name = "影视自动化"
        orch.icon = "data/icons/media-stack.svg"
        orch.app_composition = MEDIA_COMPOSITION
        orch.shared_config_schema = MEDIA_SHARED_CONFIG_SCHEMA
        await db.commit()
        print("updated media-stack")


if __name__ == "__main__":
    asyncio.run(main())
