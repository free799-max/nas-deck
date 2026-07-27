"""编排共享配置合并工具。

编排（如影视自动化）的共享配置中包含 volumes（存储映射）和 env（环境变量）
数组，需要合并进各应用自身的配置中，而不是简单浅合并——否则应用配置里的
同名字段（如应用自己的 volumes）会整体覆盖共享配置，导致共享内容不会渲染
到最终的 Compose YAML 中。

合并规则：
- 共享 volumes 追加到应用主容器的 volumes 字段，按 container_path 去重，
  并打上 shared=True 标记（模板据此跳过 project_name 前缀，相对路径直接
  相对于 Docker 挂载目录）；
- 共享 env 追加到应用主容器的 env 字段，按 key 去重；
- 应用自身配置优先于共享配置。
"""

# 各合并字段对应的去重键
_DEDUP_KEY_BY_SETTING_TYPE = {
    "volumes": "container_path",
    "env": "key",
}


def _mark_shared_items(items: list, setting_type: str) -> list:
    """为共享配置项打标。

    volumes 项附加 shared=True 标记，应用模板据此跳过 project_name 前缀，
    使相对路径直接相对于 Docker 挂载目录（共享目录不属于单个项目）。
    """
    if setting_type != "volumes":
        return items
    return [
        {**item, "shared": True} if isinstance(item, dict) else item
        for item in items
    ]


def _find_main_container(schema: dict | None, app_name: str) -> dict | None:
    """从应用 config_schema 的 containers 中找到主容器定义。

    优先匹配 name 等于应用名的容器，否则取第一个容器。
    """
    containers = (schema or {}).get("containers") or []
    if not containers:
        return None
    return next(
        (c for c in containers if c.get("name") == app_name),
        containers[0],
    )


def _get_setting_fields(
    schema: dict | None,
    setting_type: str,
    container_name: str | None = None,
) -> list[str]:
    """从 schema 的 containers 定义中提取指定类型设置项的字段名列表。

    container_name 为 None 时取所有容器的设置（用于共享配置 schema）。
    """
    fields: list[str] = []
    for container in (schema or {}).get("containers") or []:
        if container_name and container.get("name") != container_name:
            continue
        for setting in container.get("settings") or []:
            if setting.get("type") == setting_type:
                fields.extend(setting.get("fields") or [])
    return fields


def _merge_array_by_key(
    primary: list | None,
    extra: list | None,
    dedup_key: str,
) -> list:
    """合并两个对象数组，按 dedup_key 去重，primary 中的项优先。"""
    merged: list = []
    seen: set = set()
    for item in [*(primary or []), *(extra or [])]:
        if not isinstance(item, dict):
            continue
        marker = item.get(dedup_key)
        if marker in seen:
            continue
        seen.add(marker)
        merged.append(item)
    return merged


def merge_shared_config(
    shared_config: dict | None,
    app_config: dict | None,
    shared_schema: dict | None,
    app_schema: dict | None,
    app_name: str,
) -> dict:
    """将编排共享配置合并进单个应用的配置。

    先做浅合并保留标量字段的覆盖语义，再把共享的 volumes/env 数组追加到
    应用主容器对应的字段中（应用自身项优先，按 container_path/key 去重）。
    """
    shared_config = shared_config or {}
    app_config = app_config or {}
    merged = {**shared_config, **app_config}
    if not shared_config:
        return merged

    main_container = _find_main_container(app_schema, app_name)

    for setting_type, dedup_key in _DEDUP_KEY_BY_SETTING_TYPE.items():
        shared_fields = _get_setting_fields(shared_schema, setting_type)
        if not shared_fields:
            continue
        app_fields = _get_setting_fields(
            app_schema,
            setting_type,
            container_name=(main_container or {}).get("name"),
        )
        if not app_fields:
            continue
        for shared_field in shared_fields:
            shared_items = shared_config.get(shared_field)
            if not isinstance(shared_items, list):
                continue
            for app_field in app_fields:
                merged[app_field] = _merge_array_by_key(
                    app_config.get(app_field),
                    _mark_shared_items(shared_items, setting_type),
                    dedup_key,
                )

    return merged
