"""StoragePathResolver 单元测试。"""

import pytest

from app.core.exceptions import APIException
from app.services.system_config_service import StoragePathResolver


class TestStoragePathResolver:
    """测试宿主机/容器路径转换逻辑。"""

    def test_configured_property(self):
        """configured 属性反映是否已配置两个目录。"""
        assert StoragePathResolver("/mnt/data", "/mnt/data/docker").configured is True
        assert StoragePathResolver("/mnt/data", None).configured is False
        assert StoragePathResolver(None, "/mnt/data/docker").configured is False

    def test_validate_requires_both_dirs(self):
        """validate 在缺少任一配置时应抛出异常（用于实际部署校验）。"""
        with pytest.raises(APIException):
            StoragePathResolver("/mnt/data", None).validate()
        with pytest.raises(APIException):
            StoragePathResolver(None, "/mnt/data/docker").validate()

    def test_validate_requires_docker_mount_under_host_root(self):
        """Docker 挂载目录必须是宿主机根目录的子目录。"""
        with pytest.raises(APIException):
            StoragePathResolver("/mnt/data", "/opt/docker").validate()

    def test_validate_accepts_root_as_host_root_dir(self):
        """宿主机根目录为 / 时，任意非根 Docker 挂载目录应视为子目录。"""
        resolver = StoragePathResolver("/", "/opt/docker")
        resolver.validate()
        assert resolver.host_mount_base == "/opt/docker"
        assert resolver.container_mount_base == "/opt/docker"

    def test_with_defaults_uses_root_when_unconfigured(self):
        """未配置时 with_defaults 返回使用根目录的解析器，用于预览。"""
        resolver = StoragePathResolver(None, None).with_defaults()
        assert resolver.host_mount_base == "/"
        assert resolver.container_mount_base == ""

    def test_container_mount_base_when_nested(self):
        """嵌套时容器基础路径为去掉根前缀后的相对路径。"""
        resolver = StoragePathResolver("/mnt/data", "/mnt/data/docker")
        resolver.validate()
        assert resolver.host_mount_base == "/mnt/data/docker"
        assert resolver.container_mount_base == "/docker"

    def test_container_mount_base_when_same(self):
        """两者相同时容器基础路径为空。"""
        resolver = StoragePathResolver("/mnt/data", "/mnt/data")
        resolver.validate()
        assert resolver.host_mount_base == "/mnt/data"
        assert resolver.container_mount_base == ""

    def test_make_host_path(self):
        """自动生成宿主机挂载目录。"""
        resolver = StoragePathResolver("/mnt/data", "/mnt/data/docker")
        assert (
            resolver.make_host_path("moviepilot", "moviepilot", "config")
            == "/mnt/data/docker/moviepilot/moviepilot/config"
        )

    def test_make_container_path(self):
        """自动生成容器内挂载目录。"""
        resolver = StoragePathResolver("/mnt/data", "/mnt/data/docker")
        assert (
            resolver.make_container_path("moviepilot", "moviepilot", "config")
            == "/docker/moviepilot/moviepilot/config"
        )

    def test_to_container_path_under_host_root(self):
        """宿主机根目录下的路径转换为容器相对路径。"""
        resolver = StoragePathResolver("/mnt/data", "/mnt/data/docker")
        assert resolver.to_container_path("/mnt/data/movies") == "/movies"

    def test_to_container_path_for_docker_mount(self):
        """Docker 挂载目录本身转换为容器基础路径。"""
        resolver = StoragePathResolver("/mnt/data", "/mnt/data/docker")
        assert resolver.to_container_path("/mnt/data/docker") == "/docker"

    def test_to_container_path_for_container_absolute(self):
        """容器视角绝对路径保持原样。"""
        resolver = StoragePathResolver("/mnt/data", "/mnt/data/docker")
        assert resolver.to_container_path("/media") == "/media"

    def test_to_container_path_for_relative(self):
        """相对路径视为在 Docker 挂载目录下，按容器基础路径转换。"""
        resolver = StoragePathResolver("/mnt/data", "/mnt/data/docker")
        assert resolver.to_container_path("movies") == "/docker/movies"
        assert (
            resolver.to_container_path("moviepilot/moviepilot/config")
            == "/docker/moviepilot/moviepilot/config"
        )

    def test_to_host_path_for_host_absolute(self):
        """宿主机根目录下的绝对路径保持原样。"""
        resolver = StoragePathResolver("/mnt/data", "/mnt/data/docker")
        assert resolver.to_host_path("/mnt/data/movies") == "/mnt/data/movies"

    def test_to_host_path_for_container_base(self):
        """以容器基础路径开头的路径还原为宿主机路径。"""
        resolver = StoragePathResolver("/mnt/data", "/mnt/data/docker")
        assert resolver.to_host_path("/docker/movies") == "/mnt/data/docker/movies"

    def test_to_host_path_for_other_absolute(self):
        """其他绝对路径视为用户指定的宿主机路径。"""
        resolver = StoragePathResolver("/mnt/data", "/mnt/data/docker")
        assert resolver.to_host_path("/media") == "/media"

    def test_to_host_path_for_relative(self):
        """相对路径拼接到 Docker 挂载目录。"""
        resolver = StoragePathResolver("/mnt/data", "/mnt/data/docker")
        assert (
            resolver.to_host_path("movies") == "/mnt/data/docker/movies"
        )
        assert (
            resolver.to_host_path("moviepilot/moviepilot/config")
            == "/mnt/data/docker/moviepilot/moviepilot/config"
        )

    def test_to_host_path_with_root_slash(self):
        """宿主机根目录为 / 时不应产生双斜杠。"""
        resolver = StoragePathResolver("/", "/opt/docker")
        assert resolver.to_host_path("movies") == "/opt/docker/movies"
        assert (
            resolver.to_host_path("moviepilot/moviepilot/config")
            == "/opt/docker/moviepilot/moviepilot/config"
        )

    def test_to_container_path_with_root_slash(self):
        """宿主机根目录为 / 时相对路径应转换为 /opt/docker/... 容器视角。"""
        resolver = StoragePathResolver("/", "/opt/docker")
        assert resolver.to_container_path("movies") == "/opt/docker/movies"
        assert (
            resolver.to_container_path("moviepilot/moviepilot/config")
            == "/opt/docker/moviepilot/moviepilot/config"
        )

    def test_trailing_slashes_are_normalized(self):
        """尾部斜杠应被规范化。"""
        resolver = StoragePathResolver("/mnt/data/", "/mnt/data/docker/")
        resolver.validate()
        assert resolver.host_mount_base == "/mnt/data/docker"
        assert resolver.container_mount_base == "/docker"
