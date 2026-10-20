"""Compose 服务权限相关的纯工具函数：bind mount 路径提取、PUID/PGID 解析。"""

from typing import Any


def extract_bind_sources(svc: dict) -> list[str]:
    """从单个服务的 volumes 配置中提取 bind mount 的宿主机路径。"""
    sources: list[str] = []
    volumes = svc.get("volumes") or []
    if not isinstance(volumes, list):
        return sources
    for vol in volumes:
        source: str | None = None
        if isinstance(vol, str):
            # 短语法：source:target[:mode]
            parts = vol.split(":")
            if parts:
                source = parts[0].strip()
        elif isinstance(vol, dict):
            # 长语法
            if vol.get("type") == "bind" or "source" in vol:
                source = vol.get("source")
                if not source and "bind" in vol:
                    source = vol["bind"].get("source")
        if source and source.startswith("/"):
            sources.append(source)
    return sources


def parse_puid_pgid(environment: Any) -> tuple[int, int] | None:
    """解析服务环境变量中显式配置的 PUID/PGID，两者齐备才生效。"""
    env: dict[str, Any] = {}
    if isinstance(environment, dict):
        env = environment
    elif isinstance(environment, list):
        for item in environment:
            if isinstance(item, str) and "=" in item:
                key, _, value = item.partition("=")
                env[key.strip()] = value.strip()
    uid, gid = env.get("PUID"), env.get("PGID")
    if uid is None or gid is None:
        return None
    try:
        return int(uid), int(gid)
    except (TypeError, ValueError):
        return None
