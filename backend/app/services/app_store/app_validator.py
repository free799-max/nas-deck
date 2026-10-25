"""应用商店模板与配置 Schema 校验模块。

供目录同步使用，校验失败统一抛出 APIException(400)。
"""

import yaml
from jinja2 import BaseLoader, Environment
from jsonschema import ValidationError as JSONSchemaValidationError
from jsonschema import validate as jsonschema_validate

from app.core.exceptions import APIException
from app.services.system import StoragePathResolver


def extract_default_values(config_schema: dict) -> dict:
    """从 JSON Schema 的 properties 中提取各字段的 default 值。"""
    defaults: dict = {}
    for key, prop in (config_schema.get("properties") or {}).items():
        if "default" in prop:
            defaults[key] = prop["default"]
    return defaults


# JSON Schema 字段名到界面文案的映射，便于直接提示用户要补哪一项
_FIELD_LABELS = {
    "container_path": "容器路径",
    "host_path": "本地路径",
    "mode": "读写模式",
    "local_port": "本地端口",
    "container_port": "容器端口",
    "key": "变量名",
    "value": "变量值",
}
_ARRAY_LABELS = {
    "volumes": "存储空间",
    "env": "环境变量",
    "ports": "端口",
}


def format_config_validation_error(error: JSONSchemaValidationError) -> str:
    """把 JSON Schema 校验错误转换成带位置的中文提示。"""
    location_parts: list[str] = []
    for part in error.absolute_path:
        if isinstance(part, int):
            location_parts.append(f"第 {part + 1} 项")
        else:
            location_parts.append(_ARRAY_LABELS.get(str(part), str(part)))
    location = " ".join(location_parts)
    prefix = f"{location}：" if location else ""

    if error.validator == "required":
        missing = ""
        # jsonschema 的 message 形如 "'container_path' is a required property"
        if "'" in error.message:
            missing = error.message.split("'")[1]
        label = _FIELD_LABELS.get(missing, missing)
        return f"{prefix}缺少必填项「{label}」"
    return f"{prefix}{error.message}"


def validate_app_config(db_app, config: dict) -> None:
    """校验应用配置是否符合其 config_schema。

    与部署时的校验共用同一套提示，编排部署可在真正创建任何实例前
    先对全部应用做一次预检。
    """
    schema = getattr(db_app, "config_schema", None) or {}
    if not schema:
        return
    try:
        jsonschema_validate(instance=config, schema=schema)
    except JSONSchemaValidationError as e:
        display_name = getattr(db_app, "display_name", None) or getattr(
            db_app, "name", ""
        )
        raise APIException(
            f"应用「{display_name}」配置校验失败：{format_config_validation_error(e)}",
            400,
        ) from e


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

    resolver = StoragePathResolver().with_defaults()
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
