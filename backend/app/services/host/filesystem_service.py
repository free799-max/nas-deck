"""通用文件系统服务。

提供与 Docker 无关的宿主机文件系统操作，如目录浏览，
供系统设置、Docker 管理等模块复用。
"""

from pathlib import Path

from app.core.exceptions import APIException


class FilesystemService:
    """通用文件系统服务。"""

    def list_directories(self, path: str) -> dict:
        """列出指定路径下的目录条目。

        仅返回目录，不返回文件；解析真实路径以防御路径遍历。

        Args:
            path: 要浏览的目录路径

        Returns:
            dict: 包含当前路径和目录条目的字典

        Raises:
            APIException: 路径无效、不存在、不是目录或无权限访问时
        """
        try:
            target = Path(path).expanduser().resolve()
        except Exception as exc:
            raise APIException(f"无效路径: {path}", 400) from exc

        if not target.exists():
            raise APIException(f"路径不存在: {path}", 404)
        if not target.is_dir():
            raise APIException(f"不是目录: {path}", 400)

        entries = []
        try:
            for child in sorted(target.iterdir()):
                if child.is_dir():
                    entries.append({
                        "name": child.name,
                        "path": str(child.resolve()),
                        "is_directory": True,
                    })
        except PermissionError as exc:
            raise APIException(f"无权限访问路径: {path}", 403) from exc
        except OSError as exc:
            raise APIException(f"读取路径失败: {exc}", 500) from exc

        return {
            "path": str(target),
            "entries": entries,
        }


# 全局服务单例
filesystem_service = FilesystemService()
