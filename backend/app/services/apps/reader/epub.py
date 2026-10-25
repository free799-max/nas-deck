"""Reader 导出 EPUB 的规范化处理。

Reader 导出的 EPUB 偶尔包含裸 ``&`` 或非法 XML 控制字符，二毛书库的
解析器会拒绝这类文件。这里把 Book Bridge 的处理逻辑搬到后端：
- 转义裸 ``&``、剔除非法控制字符；
- 重新打包为 ``mimetype`` 首条且不压缩的标准 EPUB；
- 打包前后各做一次 XML 解析自检，结果供界面展示。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

BAD_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
BARE_AMP_RE = re.compile(r"&(?!#\d+;|#x[0-9A-Fa-f]+;|[A-Za-z][A-Za-z0-9]*;)")

MARKUP_SUFFIXES = (".html", ".xhtml", ".htm", ".xml", ".opf", ".ncx")
DEFAULT_DATE_TIME = (1980, 1, 1, 0, 0, 0)


@dataclass
class EpubFixResult:
    """一次 EPUB 规范化处理的结果。"""

    entries: int
    failures_before: list[str]
    failures_after: list[str]


def is_markup(name: str) -> bool:
    """判断 zip 条目是否需要按 XML/HTML 处理。"""
    return name.lower().endswith(MARKUP_SUFFIXES)


def clean_markup(text: str) -> str:
    """剔除非法 XML 控制字符并转义裸 ``&``。"""
    return BARE_AMP_RE.sub("&amp;", BAD_CHAR_RE.sub("", text))


def epub_failures(path: Path) -> list[str]:
    """解析 EPUB 内所有标记文件，返回无法解析的条目。"""
    failures: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir() or not is_markup(info.filename):
                    continue
                try:
                    ET.fromstring(archive.read(info.filename))
                except Exception as exc:  # noqa: BLE001 - 需要汇总任意解析错误
                    failures.append(f"{info.filename}: {_truncate(exc)}")
    except (OSError, zipfile.BadZipFile) as exc:
        failures.append(f"无法读取 EPUB: {_truncate(exc)}")
    return failures


def fix_epub(source: Path, destination: Path) -> EpubFixResult:
    """把 source 规范化为 destination，返回处理结果。"""
    failures_before = epub_failures(source)
    entries = 0
    with (
        zipfile.ZipFile(source) as archive,
        zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as output,
    ):
        names = set(archive.namelist())
        if "mimetype" in names:
            info = zipfile.ZipInfo("mimetype", date_time=DEFAULT_DATE_TIME)
            info.compress_type = zipfile.ZIP_STORED
            output.writestr(info, archive.read("mimetype"))
            entries += 1

        for info in archive.infolist():
            if info.is_dir() or info.filename == "mimetype":
                continue
            data = archive.read(info.filename)
            if is_markup(info.filename):
                text = data.decode("utf-8", errors="replace")
                data = clean_markup(text).encode("utf-8")
            out = zipfile.ZipInfo(info.filename, date_time=_date_time(info))
            out.compress_type = zipfile.ZIP_DEFLATED
            out.external_attr = info.external_attr
            output.writestr(out, data)
            entries += 1

    return EpubFixResult(entries, failures_before, epub_failures(destination))


def _date_time(info: zipfile.ZipInfo) -> tuple[int, int, int, int, int, int]:
    """zip 时间早于 1980 年时回退到固定时间。"""
    value = info.date_time
    if not value or value[0] < 1980:
        return DEFAULT_DATE_TIME
    return value


def _truncate(value: object, limit: int = 160) -> str:
    text = str(value).replace("\n", " ").replace("\r", " ")
    return text if len(text) <= limit else text[:limit] + "..."
