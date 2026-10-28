"""Compose 输出/日志处理相关的纯工具函数。"""

import re

# ANSI 转义序列（颜色、光标移动、清行等），用于清理 compose 输出中的进度条控制符
_ANSI_ESCAPE_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# 分层拉取/解压的进度刷新行，如 "ec32d732991c Downloading [==>  ] 29.36MB/530.9MB"
_PROGRESS_LINE_PATTERN = re.compile(
    r"^\s*[0-9a-f]{12}\s+(Pulling fs layer|Waiting|Downloading|Verifying Checksum|Extracting)\b"
)


def strip_ansi(text: str) -> str:
    """移除 ANSI 转义序列，避免进度条控制符污染日志。"""
    return _ANSI_ESCAPE_PATTERN.sub("", text)


def is_progress_line(line: str) -> bool:
    """判断是否为镜像分层下载/解压的进度刷新行（高频重复，不宜全量转发）。"""
    return bool(_PROGRESS_LINE_PATTERN.match(line))


def summarize_compose_error(stderr: str, max_lines: int = 8, max_chars: int = 1000) -> str:
    """从 compose 失败的 stderr 中提取有意义的错误信息。

    镜像拉取进度占 stderr 的绝大部分且全部原样累积，直接抛出会产生
    数百行刷屏的报错。优先保留非进度行；全是进度行时退化为最后一行。
    """
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    meaningful = [line for line in lines if not is_progress_line(line)]
    selected = meaningful[-max_lines:] if meaningful else lines[-1:]
    return "\n".join(selected)[:max_chars]


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
