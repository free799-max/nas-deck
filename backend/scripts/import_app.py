"""将应用商店 App 元数据从 JSON 文件导入数据库。

运行方式（在 backend/ 目录下）：
    PYTHONPATH=./app .venv/bin/python -m scripts.import_app --json /path/to/app.json

JSON 示例：
    {
        "name": "moviepilot",
        "display_name": "MoviePilot",
        "description": "...",
        "category": "media",
        "tags": ["media", "automation"],
        "website": "https://example.com",
        "source_url": "https://github.com/example/app",
        "architectures": ["amd64", "arm64"],
        "image": "example/app",
        "default_ports": [{"port": 8080, "protocol": "tcp", "description": "Web UI"}],
        "config_schema": {...},
        "yaml_template": "services:\n  app:\n    image: example/app\n...",
        "readme": "# App",
        "version": "1.0.0",
        "type": "compose",
        "changelog": "",
        "backup_paths": [],
        "is_builtin": false
    }
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError as PydanticValidationError
from sqlalchemy import select

# 确保 backend/ 在 sys.path 中，允许以 python -m scripts.import_app 方式运行
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.models  # noqa: F401 — 注册所有模型到 Base.metadata
from app.database import async_session
from app.models.app_store import App
from app.services.app_store.app_validator import validate_app_definition


class AppImportInput(BaseModel):
    """应用商店 App 导入输入模型。"""

    name: str = Field(..., min_length=1, max_length=50)
    display_name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    category: str = Field(default="other", max_length=50)
    tags: list[str] = Field(default_factory=list)
    icon: str | None = Field(default=None, max_length=255)
    website: str | None = Field(default=None, max_length=255)
    source_url: str | None = Field(default=None, max_length=255)
    architectures: list[str] = Field(default_factory=lambda: ["amd64", "arm64"])
    image: str | None = Field(default=None, max_length=255)
    default_ports: list[dict] = Field(default_factory=list)
    config_schema: dict = Field(default_factory=dict)
    yaml_template: str
    readme: str | None = None
    version: str = Field(default="1.0.0", max_length=20)
    type: str = Field(default="compose", max_length=20)
    changelog: str | None = None
    backup_paths: list[str] = Field(default_factory=list)
    is_builtin: bool = False


def _load_input(json_path: Path) -> AppImportInput:
    """从 JSON 文件加载并校验输入。"""
    if not json_path.exists():
        raise FileNotFoundError(f"JSON 文件不存在: {json_path}")

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败: {e}") from e

    try:
        return AppImportInput.model_validate(data)
    except PydanticValidationError as e:
        raise ValueError(f"输入字段校验失败:\n{e}") from e


async def import_app(json_path: Path) -> App:
    """将 JSON 描述的应用导入 apps 表。"""
    app_input = _load_input(json_path)

    validate_app_definition(
        app_input.yaml_template, app_input.config_schema, app_input.image or ""
    )

    async with async_session() as db:
        existing = await db.execute(select(App).where(App.name == app_input.name))
        if existing.scalar_one_or_none():
            raise ValueError(f"应用 '{app_input.name}' 已存在，跳过导入")

        app = App(
            name=app_input.name,
            display_name=app_input.display_name,
            description=app_input.description,
            category=app_input.category,
            tags=app_input.tags,
            icon=app_input.icon,
            website=app_input.website,
            source_url=app_input.source_url,
            architectures=app_input.architectures,
            image=app_input.image,
            default_ports=app_input.default_ports,
            config_schema=app_input.config_schema,
            yaml_template=app_input.yaml_template,
            readme=app_input.readme,
            version=app_input.version,
            type=app_input.type,
            changelog=app_input.changelog,
            backup_paths=app_input.backup_paths,
            is_builtin=app_input.is_builtin,
        )
        db.add(app)
        await db.commit()
        await db.refresh(app)
        return app


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="将应用商店 App 元数据从 JSON 导入数据库")
    parser.add_argument("--json", required=True, type=Path, help="应用元数据 JSON 文件路径")
    args = parser.parse_args()

    try:
        imported = asyncio.run(import_app(args.json))
        print(f"成功导入应用: id={imported.id}, name={imported.name}, display_name={imported.display_name}")
    except Exception as e:
        print(f"导入失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
