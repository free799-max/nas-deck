"""初始化漫画自动化组合模板数据。

运行方式（在 backend/ 目录下）：
    PYTHONPATH=. .venv/bin/python -m scripts.init_comics_orchestration

脚本幂等：同名模板已存在时更新组合定义与共享配置。
依赖应用商店中已存在 comic-auto / komga / kavita 三个应用，
缺失时请先执行 ``scripts/import_apps_batch``。
"""

import sys
from pathlib import Path

# 将项目根目录加入路径，支持从 scripts/ 子目录运行
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio

from sqlalchemy import select

from app.database import async_session
from app.models.app_store import App
from app.models.orchestration import AppOrchestration

ORCHESTRATION_NAME = "comics-stack"

# Comic Auto 下载目录与 Komga / Kavita 媒体库目录保持同一路径：
# 编排把共享存储统一挂载到 /mnt/media，下载到 /mnt/media/down 后
# 媒体库可直接扫描同一目录完成入库。
_COMIC_LIBRARY_PATH = "/mnt/media/down"
_COMIC_CACHE_PATH = "/mnt/media/cache"

COMICS_COMPOSITION = [
    {
        "app_name": "comic-auto",
        "relation": "required",
        # 部署后自动装配：把 Komga / Kavita（实际部署的那个）配为媒体服务器，
        # 并同步写入 Comic Auto 的下载/缓存目录。
        "integrations": [
            {
                "type": "mediaserver",
                "from": "komga",
                "library_path": _COMIC_LIBRARY_PATH,
                "download_dir": _COMIC_LIBRARY_PATH,
                "cache_dir": _COMIC_CACHE_PATH,
            },
            {
                "type": "mediaserver",
                "from": "kavita",
                "library_path": _COMIC_LIBRARY_PATH,
                "download_dir": _COMIC_LIBRARY_PATH,
                "cache_dir": _COMIC_CACHE_PATH,
            },
        ],
    },
    {"app_name": "komga", "relation": "optional", "group": "reader"},
    {"app_name": "kavita", "relation": "optional", "group": "reader"},
]

COMICS_SHARED_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "volumes": {
            "type": "array",
            "title": "存储空间设置",
            "description": "漫画自动化各应用共享的漫画目录（下载目录 = 媒体库目录）",
            "default": [
                {"mode": "rw", "host_path": "comics", "container_path": "/mnt/media"},
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
            "description": "漫画自动化各应用共享的环境变量",
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
            "description": "所有漫画自动化应用共享的漫画目录和环境变量",
            "settings": [
                {"type": "volumes", "title": "存储空间设置", "fields": ["volumes"]},
                {"type": "env", "title": "环境变量", "fields": ["env"]},
            ],
        }
    ],
}

REQUIRED_APPS = ("comic-auto", "komga", "kavita")


async def main() -> int:
    async with async_session() as db:
        result = await db.execute(
            select(App.name).where(App.name.in_(REQUIRED_APPS))
        )
        existing_apps = {row[0] for row in result}
        missing = [name for name in REQUIRED_APPS if name not in existing_apps]
        if missing:
            print(
                "缺少应用商店数据: "
                + ", ".join(missing)
                + "\n请先执行: PYTHONPATH=. .venv/bin/python -m scripts.import_apps_batch"
            )
            return 1

        result = await db.execute(
            select(AppOrchestration).where(
                AppOrchestration.name == ORCHESTRATION_NAME
            )
        )
        orch = result.scalar_one_or_none()
        if orch is None:
            orch = AppOrchestration(name=ORCHESTRATION_NAME)
            db.add(orch)

        orch.display_name = "漫画自动化"
        orch.description = (
            "一键搭建漫画自动化：Comic Auto 订阅、下载、追更并刮削漫画，"
            "Komga / Kavita 提供在线阅读，部署完成即可开始阅读。"
        )
        orch.category = "comics"
        orch.tags = ["漫画", "comic-auto", "komga", "kavita", "订阅追更", "下载"]
        # 使用前端 public 下的静态图标，避免依赖运行时 data 目录
        orch.icon = "/icons/orchestrations/comics-stack.svg"
        orch.website = "https://comic.freeapps.uk/guide/"
        orch.source_url = None
        orch.version = "1.0.0"
        orch.is_builtin = True
        orch.app_composition = COMICS_COMPOSITION
        orch.shared_config_schema = COMICS_SHARED_CONFIG_SCHEMA

        await db.commit()
        print(f"已写入 {ORCHESTRATION_NAME}（漫画自动化）")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
