"""批量导入/更新应用商店 App 元数据（upsert）。

扫描 scripts/apps_data/ 下的 *.json（忽略 _ 开头的文件），逐个执行与
scripts/import_app.py 相同的校验；同名应用已存在则更新字段，否则插入。

运行方式（在 backend/ 目录下）：
    PYTHONPATH=. .venv/bin/python -m scripts.import_apps_batch
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# 确保 backend/ 在 sys.path 中，允许以 python -m scripts.import_apps_batch 方式运行
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.models  # noqa: F401 — 注册所有模型到 Base.metadata
from app.database import async_session
from app.models.app_store import App
from app.services.app_store.app_validator import validate_app_definition
from scripts.import_app import AppImportInput
from sqlalchemy import select

DATA_DIR = Path(__file__).resolve().parent / "apps_data"

UPDATE_FIELDS = [
    "display_name",
    "description",
    "category",
    "tags",
    "icon",
    "website",
    "source_url",
    "architectures",
    "image",
    "default_ports",
    "config_schema",
    "yaml_template",
    "readme",
    "version",
    "type",
    "changelog",
    "backup_paths",
    "is_builtin",
]


async def import_all() -> int:
    json_files = sorted(
        p for p in DATA_DIR.glob("*.json") if not p.name.startswith("_")
    )
    if not json_files:
        print(f"未找到应用 JSON: {DATA_DIR}")
        return 1

    created, updated, failed = 0, 0, 0
    async with async_session() as db:
        for json_path in json_files:
            name = json_path.stem
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                app_input = AppImportInput.model_validate(data)
                validate_app_definition(
                    app_input.yaml_template,
                    app_input.config_schema,
                    app_input.image or "",
                )

                existing = await db.execute(
                    select(App).where(App.name == app_input.name)
                )
                app = existing.scalar_one_or_none()
                if app is None:
                    app = App(name=app_input.name)
                    for field in UPDATE_FIELDS:
                        setattr(app, field, getattr(app_input, field))
                    db.add(app)
                    created += 1
                    action = "新增"
                else:
                    for field in UPDATE_FIELDS:
                        setattr(app, field, getattr(app_input, field))
                    updated += 1
                    action = "更新"
                print(f"[{action}] {app_input.name} ({app_input.display_name})")
            except Exception as e:
                failed += 1
                print(f"[失败] {name}: {e}", file=sys.stderr)

        if failed:
            await db.rollback()
            print(f"\n存在失败项，已回滚全部变更。新增 {created}，更新 {updated}，失败 {failed}")
            return 1

        await db.commit()
    print(f"\n完成：新增 {created}，更新 {updated}，失败 {failed}，总计 {len(json_files)}")
    return 0


def main() -> None:
    sys.exit(asyncio.run(import_all()))


if __name__ == "__main__":
    main()
