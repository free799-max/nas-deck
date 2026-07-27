"""应用商店模板与配置 Schema 校验模块。

供 API（创建/更新应用）与 scripts/import_app.py CLI 导入共用的校验逻辑，
校验失败统一抛出 APIException(400)。
"""

import yaml
from jinja2 import BaseLoader, Environment
from jsonschema import ValidationError as JSONSchemaValidationError
from jsonschema import validate as jsonschema_validate

from app.core.exceptions import APIException
from app.services.system_config_service import StoragePathResolver


def extract_default_values(config_schema: dict) -> dict:
    """从 JSON Schema 的 properties 中提取各字段的 default 值。"""
    defaults: dict = {}
    for key, prop in (config_schema.get("properties") or {}).items():
        if "default" in prop:
            defaults[key] = prop["default"]
    return defaults


def validate_config_schema(config_schema: dict) -> None:
    """校验 config_schema 自身合法，且默认配置可通过校验。"""
    if not config_schema:
        return

    if "type" not in config_schema:
        raise APIException("config_schema 必须包含 type 字段", 400)

    defaults = extract_default_values(config_schema)

    try:
        jsonschema_validate(instance=defaults, schema=config_schema)
    except JSONSchemaValidationError as e:
        raise APIException(f"config_schema 默认值校验失败: {e.message}", 400) from e


def validate_yaml_template(yaml_template: str, config_schema: dict, image: str = "") -> None:
    """先用默认值渲染 Jinja2 模板，再校验结果是否为合法 YAML。"""
    default_values = extract_default_values(config_schema or {})
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
        raise APIException(f"yaml_template Jinja2 渲染失败: {e}", 400) from e

    try:
        yaml.safe_load(rendered)
    except yaml.YAMLError as e:
        raise APIException(f"渲染后的结果不是合法 YAML: {e}", 400) from e


def validate_app_definition(yaml_template: str, config_schema: dict, image: str = "") -> None:
    """校验应用定义的完整组合：config_schema 与 yaml_template。"""
    validate_config_schema(config_schema)
    validate_yaml_template(yaml_template, config_schema, image)
