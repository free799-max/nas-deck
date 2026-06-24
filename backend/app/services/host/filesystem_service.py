"""通用文件系统服务。

提供与 Docker 无关的宿主机文件系统操作，如目录浏览、创建、重命名、删除，
供系统设置、Docker 管理等模块复用。
"""

import shutil
from pathlib import Path

from app.core.exceptions import APIException


class FilesystemService:
    """通用文件系统服务。"""

    def _resolve_and_defend(
        self,
        path: str,
        root_path: str | None,
        strict: bool = True,
    ) -> Path:
        """解析路径并做路径遍历防护。

        Args:
            path: 用户传入的路径
            root_path: 允许访问的根目录，若提供则目标路径必须位于其下
            strict: 是否要求路径已存在（Path.resolve 的 strict 参数）

        Returns:
            Path: 解析后的真实路径

        Raises:
            APIException: 路径无效或越界时
        """
        try:
            target = Path(path).expanduser().resolve(strict=strict)
        except FileNotFoundError:
            # resolve(strict=True) 对不存在的路径会抛 FileNotFoundError；
            # 这里转为通用无效路径异常，让调用方按需处理。
            raise APIException(f"路径不存在: {path}", 404)
        except Exception as exc:
            raise APIException(f"无效路径: {path}", 400) from exc

        if root_path:
            try:
                root = Path(root_path).expanduser().resolve()
            except Exception as exc:
                raise APIException(f"无效根目录: {root_path}", 400) from exc
            if not target.is_relative_to(root):
                raise APIException("路径越界，禁止访问该目录", 403)

        return target

    def list_directories(self, path: str, root_path: str | None = None) -> dict:
        """列出指定路径下的目录条目。

        仅返回目录，不返回文件；解析真实路径以防御路径遍历。

        Args:
            path: 要浏览的目录路径
            root_path: 允许访问的根目录

        Returns:
            dict: 包含当前路径和目录条目的字典

        Raises:
            APIException: 路径无效、不存在、不是目录或无权限访问时
        """
        target = self._resolve_and_defend(path, root_path)

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

    def create_directory(self, path: str, root_path: str | None = None) -> dict:
        """创建目录。

        Args:
            path: 要创建的目录完整路径
            root_path: 允许访问的根目录

        Returns:
            dict: 新目录条目

        Raises:
            APIException: 路径越界、父目录不存在、目录已存在或创建失败时
        """
        # 目标路径可能不存在，使用 strict=False 做遍历防护
        target = self._resolve_and_defend(path, root_path, strict=False)

        if target.exists():
            raise APIException(f"目录已存在: {path}", 409)

        parent = target.parent
        if not parent.exists() or not parent.is_dir():
            raise APIException(f"父目录不存在: {parent}", 400)

        try:
            target.mkdir(parents=False, exist_ok=False)
        except PermissionError as exc:
            raise APIException(f"无权限创建目录: {path}", 403) from exc
        except OSError as exc:
            raise APIException(f"创建目录失败: {exc}", 500) from exc

        return {
            "name": target.name,
            "path": str(target),
            "is_directory": True,
        }

    def rename_directory(
        self,
        old_path: str,
        new_name: str,
        root_path: str | None = None,
    ) -> dict:
        """重命名目录。

        Args:
            old_path: 原目录路径
            new_name: 新目录名（仅名称，不含路径）
            root_path: 允许访问的根目录

        Returns:
            dict: 新目录条目

        Raises:
            APIException: 路径越界、原目录不存在、目标已存在或重命名失败时
        """
        source = self._resolve_and_defend(old_path, root_path)
        if not source.is_dir():
            raise APIException(f"不是目录: {old_path}", 400)

        destination = source.parent / new_name
        # 目标可能不存在，使用 strict=False 做遍历防护
        self._resolve_and_defend(str(destination), root_path, strict=False)

        if destination.exists():
            raise APIException(f"目标目录已存在: {new_name}", 409)

        try:
            source.rename(destination)
        except PermissionError as exc:
            raise APIException(f"无权限重命名目录: {old_path}", 403) from exc
        except OSError as exc:
            raise APIException(f"重命名目录失败: {exc}", 500) from exc

        return {
            "name": destination.name,
            "path": str(destination),
            "is_directory": True,
        }

    def delete_directory(self, path: str, root_path: str | None = None) -> None:
        """删除目录（递归删除非空目录）。

        Args:
            path: 要删除的目录路径
            root_path: 允许访问的根目录

        Raises:
            APIException: 路径越界、不存在、不是目录或删除失败时
        """
        target = self._resolve_and_defend(path, root_path)
        if not target.is_dir():
            raise APIException(f"不是目录: {path}", 400)

        try:
            shutil.rmtree(target)
        except PermissionError as exc:
            raise APIException(f"无权限删除目录: {path}", 403) from exc
        except OSError as exc:
            raise APIException(f"删除目录失败: {exc}", 500) from exc


# 全局服务单例
filesystem_service = FilesystemService()
