"""Compose 输出/日志处理相关的纯工具函数。"""

import re

# ANSI 转义序列（颜色、光标移动、清行等），用于清理 compose 输出中的进度条控制符
_ANSI_ESCAPE_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    """移除 ANSI 转义序列，避免进度条控制符污染日志。"""
    return _ANSI_ESCAPE_PATTERN.sub("", text)


def detect_stage(line: str) -> str | None:
    """根据 compose 输出行推断当前阶段。"""
    lowered = line.lower()
    if any(k in lowered for k in ("pulling", "downloading", "extracting", "already exists", "pulled")):
        return "pulling_images"
    if any(k in lowered for k in ("preparing packages", "preparing metadata", "building wheel", "installing")):
        return "preparing_packages"
    if any(k in lowered for k in ("creating", "starting", "started", "container", "running")):
        return "starting_services"
    return None
