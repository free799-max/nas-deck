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
    "type": "object",
    "properties": {
        "volumes": {
            "type": "array",
            "title": "存储空间设置",
            "description": "影视自动化各应用共享的存储映射",
            "default": [
                {"mode": "rw", "host_path": "media", "container_path": "/media"},
                {"mode": "rw", "host_path": "downloads", "container_path": "/downloads"},
            ],
            "items": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "title": "读写模式",
                        "enum": ["rw", "ro"],
                        "default": "rw",
                    },
                    "host_path": {
                        "type": "string",
                        "title": "本地路径",
                        "format": "directory",
                    },
                    "container_path": {
                        "type": "string",
                        "title": "容器路径",
                    },
                },
                "required": ["host_path", "container_path", "mode"],
            },
        },
        "env": {
            "type": "array",
            "title": "环境变量",
            "description": "影视自动化各应用共享的环境变量",
            "default": [
                {"key": "TZ", "value": "Asia/Shanghai"},
            ],
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "title": "变量名"},
                    "value": {"type": "string", "title": "值"},
                },
                "required": ["key", "value"],
            },
        },
    },
    "required": ["volumes", "env"],
    "containers": [
        {
            "name": "shared",
            "title": "公共配置",
            "description": "所有影视自动化应用共享的存储空间和环境变量",
            "settings": [
                {"type": "volumes", "title": "存储空间设置", "fields": ["volumes"]},
                {"type": "env", "title": "环境变量", "fields": ["env"]},
            ],
        }
    ],
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
