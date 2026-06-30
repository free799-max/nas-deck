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

import yaml
from jinja2 import Environment, BaseLoader
from jsonschema import validate as jsonschema_validate, ValidationError as JSONSchemaValidationError
from pydantic import BaseModel, Field, ValidationError as PydanticValidationError
from sqlalchemy import select

# 确保 backend/ 在 sys.path 中，允许以 python -m scripts.import_app 方式运行
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.models  # noqa: F401 — 注册所有模型到 Base.metadata
from app.database import async_session
from app.models.app_store import App


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


from app.services.system_config_service import StoragePathResolver


def _extract_default_values(config_schema: dict) -> dict:
    """从 JSON Schema 的 properties 中提取各字段的 default 值。"""
    defaults: dict = {}
    for key, prop in (config_schema.get("properties") or {}).items():
        if "default" in prop:
            defaults[key] = prop["default"]
    return defaults


def _validate_yaml_template(yaml_template: str, config_schema: dict, image: str = "") -> None:
    """先用默认值渲染 Jinja2 模板，再校验结果是否为合法 YAML。"""
    default_values = _extract_default_values(config_schema or {})
    merged = {
        **default_values,
        "project_name": "test-project",
        "app_name": "test-app",
        "image": image or "example/image",
    }

    resolver = StoragePathResolver(None, None).with_defaults()
    try:
        env = Environment(loader=BaseLoader(), autoescape=False)
        env.globals["make_host_path"] = resolver.make_host_path
        env.globals["make_container_path"] = resolver.make_container_path
        env.globals["to_host_path"] = resolver.to_host_path
        env.globals["to_container_path"] = resolver.to_container_path
        rendered = env.from_string(yaml_template).render(merged)
    except Exception as e:
        raise ValueError(f"yaml_template Jinja2 渲染失败: {e}") from e

    try:
        yaml.safe_load(rendered)
    except yaml.YAMLError as e:
        raise ValueError(f"渲染后的结果不是合法 YAML: {e}") from e


def _validate_config_schema(config_schema: dict) -> None:
    """校验 config_schema 自身合法，且默认配置可通过校验。"""
    if not config_schema:
        return

    if "type" not in config_schema:
        raise ValueError("config_schema 必须包含 type 字段")

    defaults: dict = {}
    properties = config_schema.get("properties") or {}
    for key, prop in properties.items():
        if "default" in prop:
            defaults[key] = prop["default"]

    try:
        jsonschema_validate(instance=defaults, schema=config_schema)
    except JSONSchemaValidationError as e:
        raise ValueError(f"config_schema 默认值校验失败: {e.message}") from e


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

    _validate_yaml_template(app_input.yaml_template, app_input.config_schema, app_input.image)
    _validate_config_schema(app_input.config_schema)

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
