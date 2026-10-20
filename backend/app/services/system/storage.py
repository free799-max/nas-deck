"""存储路径解析器。

负责宿主机真实路径与容器视角路径之间的互相转换：
- 宿主机基础路径 = storage_docker_mount_dir
- 容器基础路径 = storage_docker_mount_dir 去掉 storage_host_root_dir 前缀
"""

from pathlib import Path

from app.core.exceptions import APIException


class StoragePathResolver:
    """存储路径解析器。

    负责宿主机真实路径与容器视角路径之间的互相转换：
    - 宿主机基础路径 = storage_docker_mount_dir
    - 容器基础路径 = storage_docker_mount_dir 去掉 storage_host_root_dir 前缀
    """

    def __init__(
        self,
        host_root_dir: str | None,
        docker_mount_dir: str | None,
    ):
        def _normalize(path: str | None) -> str:
            if not path:
                return ""
            value = path.strip().rstrip("/")
            return value if value else "/"

        self.host_root_dir = _normalize(host_root_dir)
        self.docker_mount_dir = _normalize(docker_mount_dir)

    @staticmethod
    def _join(base: str, path: str) -> str:
        """拼接基础路径与后续路径，避免产生双斜杠或丢失根目录。"""
        if not base or not path:
            return base or path or ""
        path = path.lstrip("/")
        if base.endswith("/"):
            return base + path
        return f"{base}/{path}"

    @property
    def configured(self) -> bool:
        """是否已配置宿主机根目录和 Docker 挂载目录。"""
        return bool(self.host_root_dir and self.docker_mount_dir)

    def validate(self) -> None:
        """校验两个目录是否已配置且满足前缀关系。"""
        if not self.configured:
            raise APIException(
                "未配置宿主机根目录和 Docker 挂载目录，请前往系统设置-基础设置配置", 400
            )
        if self.docker_mount_dir != self.host_root_dir:
            try:
                Path(self.docker_mount_dir).relative_to(Path(self.host_root_dir))
            except ValueError:
                raise APIException(
                    "Docker 挂载目录必须是宿主机根目录的子目录", 400
                )

    def with_defaults(self) -> "StoragePathResolver":
        """返回使用默认根目录的解析器，用于未配置时的预览。

        默认使用根目录 "/"，让 preview 仍可生成可读的 YAML，
        实际部署前仍需在系统设置中配置真实路径。
        """
        if self.configured:
            return self
        return StoragePathResolver("/", "/")

    @property
    def host_mount_base(self) -> str:
        """宿主机视角的 Docker 挂载基础目录。"""
        return self.docker_mount_dir

    @property
    def container_mount_base(self) -> str:
        """容器视角的 Docker 挂载基础目录（去掉宿主机根前缀，保留前导 /）。"""
        if self.docker_mount_dir == self.host_root_dir:
            return ""
        base = self.docker_mount_dir[len(self.host_root_dir) :]
        if base.startswith("/"):
            return base
        return f"/{base}"

    def make_host_path(
        self,
        app_name: str,
        service_name: str,
        mount_name: str,
    ) -> str:
        """按规则生成宿主机上的自动挂载目录。"""
        return self._join(
            self.docker_mount_dir,
            f"{app_name}/{service_name}/{mount_name}",
        )

    def make_container_path(
        self,
        app_name: str,
        service_name: str,
        mount_name: str,
    ) -> str:
        """按规则生成容器内的自动挂载目录。"""
        base = self.container_mount_base
        return self._join(base or "/", f"{app_name}/{service_name}/{mount_name}")

    def to_container_path(self, path: str) -> str:
        """将用户填写或选择的路径转换为容器内路径。

        - 以宿主机根目录开头的绝对路径：去掉该前缀。
        - 以 Docker 挂载目录开头的绝对路径：按容器挂载基础路径转换。
        - 以容器挂载基础路径开头的路径：保持原样。
        - 其他绝对路径（如 /media）：保持原样。
        - 相对路径：视为在 Docker 挂载目录下的相对路径，转换为容器视角。
        """
        path = (path or "").strip().rstrip("/")
        if not path:
            return ""

        # 宿主机根目录下的路径
        if path == self.host_root_dir:
            return ""
        if path.startswith(self.host_root_dir + "/"):
            suffix = path[len(self.host_root_dir) + 1 :]
            return self._join("/", suffix)

        # Docker 挂载目录下的绝对路径（宿主机根目录不是其前缀时，如两者相同）
        if path == self.docker_mount_dir or path.startswith(
            self.docker_mount_dir + "/"
        ):
            suffix = path[len(self.docker_mount_dir) :].lstrip("/")
            return self._join(self.container_mount_base or "/", suffix)

        # 容器视角的挂载基础路径
        container_base = self.container_mount_base
        if container_base and (
            path == container_base or path.startswith(container_base + "/")
        ):
            return path

        # 其他绝对路径保持原样
        if path.startswith("/"):
            return path

        # 相对路径视为在 Docker 挂载目录下
        return self._join(self.container_mount_base or "/", path)

    def to_host_path(self, path: str) -> str:
        """将用户填写或选择的路径还原为宿主机绝对路径。

        - 已是宿主机根目录下的绝对路径：原样返回。
        - 以容器挂载基础路径开头的路径：还原为宿主机根目录下的路径。
        - 其他绝对路径（如 /media）：保持原样，视为用户指定的宿主机路径。
        - 相对路径：拼接到 Docker 挂载目录下。
        """
        path = (path or "").strip().rstrip("/")
        if not path:
            return ""

        # 已是宿主机根目录下的路径
        if path == self.host_root_dir or path.startswith(self.host_root_dir + "/"):
            return path

        # 以容器挂载基础路径开头的路径，还原为宿主机根目录下的路径
        container_base = self.container_mount_base
        if container_base and (
            path == container_base or path.startswith(container_base + "/")
        ):
            return self._join(self.host_root_dir, path)

        # 其他容器内绝对路径，保持原样作为宿主机路径
        if path.startswith("/"):
            return path

        # 相对路径，拼接到 Docker 挂载目录
        return self._join(self.docker_mount_dir, path)
