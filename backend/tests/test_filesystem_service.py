"""FilesystemService 单元测试。"""

import pytest

from app.core.exceptions import APIException
from app.services.host.filesystem_service import FilesystemService


class TestFilesystemService:
    """测试通用文件系统服务。"""

    def test_list_directories(self, tmp_path):
        """列出目录条目。"""
        service = FilesystemService()
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        (tmp_path / "file.txt").write_text("x")

        result = service.list_directories(str(tmp_path))

        assert result["path"] == str(tmp_path)
        names = {e["name"] for e in result["entries"]}
        assert names == {"a", "b"}

    def test_list_directories_with_root_path_defense(self, tmp_path):
        """超出 root_path 的路径应被禁止。"""
        service = FilesystemService()
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        outside = tmp_path / ".." / "outside"

        with pytest.raises(APIException):
            service.list_directories(str(outside), root_path=str(allowed))

    def test_list_directories_with_root_path_slash(self, tmp_path):
        """root_path 为 / 时不应误判子目录越界。"""
        service = FilesystemService()
        (tmp_path / "subdir").mkdir()

        result = service.list_directories(str(tmp_path), root_path="/")

        assert result["path"] == str(tmp_path)
        names = {e["name"] for e in result["entries"]}
        assert "subdir" in names

    def test_create_directory(self, tmp_path):
        """创建目录。"""
        service = FilesystemService()
        result = service.create_directory(
            str(tmp_path / "newdir"),
            root_path=str(tmp_path),
        )
        assert result["name"] == "newdir"
        assert (tmp_path / "newdir").is_dir()

    def test_create_directory_already_exists(self, tmp_path):
        """目录已存在时报错。"""
        service = FilesystemService()
        (tmp_path / "exists").mkdir()

        with pytest.raises(APIException):
            service.create_directory(
                str(tmp_path / "exists"),
                root_path=str(tmp_path),
            )

    def test_create_directory_parent_missing(self, tmp_path):
        """父目录不存在时报错。"""
        service = FilesystemService()

        with pytest.raises(APIException):
            service.create_directory(
                str(tmp_path / "missing" / "child"),
                root_path=str(tmp_path),
            )

    def test_create_directory_traversal_defense(self, tmp_path):
        """创建目录时路径越界应被禁止。"""
        service = FilesystemService()

        with pytest.raises(APIException):
            service.create_directory(
                "/etc/nasdeck-test-dir",
                root_path=str(tmp_path),
            )

    def test_rename_directory(self, tmp_path):
        """重命名目录。"""
        service = FilesystemService()
        (tmp_path / "old").mkdir()

        result = service.rename_directory(
            str(tmp_path / "old"),
            "new",
            root_path=str(tmp_path),
        )

        assert result["name"] == "new"
        assert (tmp_path / "new").is_dir()
        assert not (tmp_path / "old").exists()

    def test_rename_directory_target_exists(self, tmp_path):
        """重命名目标已存在时报错。"""
        service = FilesystemService()
        (tmp_path / "old").mkdir()
        (tmp_path / "new").mkdir()

        with pytest.raises(APIException):
            service.rename_directory(
                str(tmp_path / "old"),
                "new",
                root_path=str(tmp_path),
            )

    def test_rename_directory_traversal_defense(self, tmp_path):
        """重命名时路径越界应被禁止。"""
        service = FilesystemService()

        with pytest.raises(APIException):
            service.rename_directory(
                "/etc",
                "new",
                root_path=str(tmp_path),
            )

    def test_delete_directory(self, tmp_path):
        """删除目录（含非空）。"""
        service = FilesystemService()
        (tmp_path / "del" / "sub").mkdir(parents=True)
        (tmp_path / "del" / "file.txt").write_text("x")

        service.delete_directory(
            str(tmp_path / "del"),
            root_path=str(tmp_path),
        )

        assert not (tmp_path / "del").exists()

    def test_delete_directory_traversal_defense(self, tmp_path):
        """删除时路径越界应被禁止。"""
        service = FilesystemService()

        with pytest.raises(APIException):
            service.delete_directory(
                "/etc",
                root_path=str(tmp_path),
            )
