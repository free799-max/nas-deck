"""系统全局配置服务。

提供系统配置的获取、初始化和更新能力。
整个系统只维护一条配置记录（id=1）。
"""

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import APIException
from app.models.system_config import SystemConfig
from app.schemas.system_config import SystemConfigUpdate


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
        if (
            self.docker_mount_dir != self.host_root_dir
            and not self.docker_mount_dir.startswith(self.host_root_dir + "/")
        ):
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
        """容器视角的 Docker 挂载基础目录（去掉宿主机根前缀）。"""
        if self.docker_mount_dir == self.host_root_dir:
            return ""
        return self.docker_mount_dir[len(self.host_root_dir) :]

    def make_host_path(
        self,
        app_name: str,
        service_name: str,
        mount_name: str,
    ) -> str:
        """按规则生成宿主机上的自动挂载目录。"""
        base = self.docker_mount_dir.rstrip("/")
        return f"{base}/{app_name}/{service_name}/{mount_name}"

    def make_container_path(
        self,
        app_name: str,
        service_name: str,
        mount_name: str,
    ) -> str:
        """按规则生成容器内的自动挂载目录。"""
        base = self.container_mount_base.rstrip("/")
        return f"{base}/{app_name}/{service_name}/{mount_name}"

    def to_container_path(self, path: str) -> str:
        """将用户填写或选择的路径转换为容器内路径。

        - 以宿主机根目录开头的绝对路径：去掉该前缀。
        - 普通相对路径：视为在容器挂载基础目录下的相对路径，补上前导 /。
        - 其他绝对路径（如 /media）：保持原样。
        """
        path = (path or "").strip().rstrip("/")
        if not path:
            return ""
        if path == self.host_root_dir:
            return ""
        if path.startswith(self.host_root_dir + "/"):
            return path[len(self.host_root_dir) :]
        if path.startswith("/"):
            return path
        return f"/{path}"

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
        if path.startswith(self.host_root_dir + "/") or path == self.host_root_dir:
            return path

        # 以容器挂载基础路径开头的路径，还原为宿主机路径
        container_base = self.container_mount_base
        if container_base and (
            path == container_base
            or path.startswith(container_base.rstrip("/") + "/")
        ):
            relative = path[len(container_base.rstrip("/")) :]
            return f"{self.docker_mount_dir}{relative}"

        # 其他容器内绝对路径，保持原样作为宿主机路径
        if path.startswith("/"):
            return path

        # 相对路径，拼接到 Docker 挂载目录
        return f"{self.docker_mount_dir}/{path}"


class SystemConfigService:
    """系统全局配置服务。"""

    # 常见 NAS 存储路径候选，按优先级排列
    _STORAGE_CANDIDATES: list[tuple[str, str]] = [
        ("/volume1", "/volume1/docker"),
        ("/mnt/data", "/mnt/data/docker"),
        ("/data", "/data/docker"),
    ]

    def _detect_default_storage_dirs(self) -> tuple[str | None, str | None]:
        """探测常见 NAS 默认存储目录，返回 (host_root_dir, docker_mount_dir)。"""
        for host_root, docker_mount in self._STORAGE_CANDIDATES:
            host_path = Path(host_root)
            if not host_path.is_dir():
                continue
            # 优先使用预置的 Docker 挂载目录
            docker_path = Path(docker_mount)
            if docker_path.is_dir() or docker_path.parent == host_path:
                return host_root, docker_mount
            # 回退到 host_root/docker
            fallback = host_path / "docker"
            if fallback.is_dir() or True:  # 允许目录不存在，后续部署时自动创建
                return host_root, str(fallback)
        return None, None

    async def get_or_create(self, db: AsyncSession) -> SystemConfig:
        """获取系统配置，不存在则创建默认记录。

        首次创建时会自动探测常见存储目录并填充默认值。

        Args:
            db: 异步数据库会话

        Returns:
            SystemConfig: 系统配置对象
        """
        result = await db.execute(select(SystemConfig).where(SystemConfig.id == 1))
        config = result.scalar_one_or_none()
        if config is None:
            host_root, docker_mount = self._detect_default_storage_dirs()
            config = SystemConfig(
                id=1,
                storage_host_root_dir=host_root,
                storage_docker_mount_dir=docker_mount,
            )
            db.add(config)
            await db.flush()
            await db.refresh(config)
        return config

    async def update(
        self, db: AsyncSession, data: SystemConfigUpdate
    ) -> SystemConfig:
        """更新系统配置。

        Args:
            db: 异步数据库会话
            data: 配置更新数据

        Returns:
            SystemConfig: 更新后的配置对象
        """
        config = await self.get_or_create(db)

        update_fields = [
            "http_proxy",
            "https_proxy",
            "no_proxy",
            "storage_host_root_dir",
            "storage_docker_mount_dir",
        ]
        for field in update_fields:
            value = getattr(data, field)
            if value is not None:
                setattr(config, field, value.strip() if value else None)

        await db.flush()
        await db.refresh(config)
        return config

    def to_dict(self, config: SystemConfig) -> dict:
        """将配置对象转换为前端友好的字典。

        Args:
            config: 系统配置对象

        Returns:
            dict: 包含 id、代理配置、配置数据目录、存储目录的字典
        """
        return {
            "id": config.id,
            "http_proxy": config.http_proxy,
            "https_proxy": config.https_proxy,
            "no_proxy": config.no_proxy,
            "storage_host_root_dir": config.storage_host_root_dir,
            "storage_docker_mount_dir": config.storage_docker_mount_dir,
        }

    def validate_directories(self, config: SystemConfig) -> None:
        """校验配置的目录是否都存在且为目录。

        Args:
            config: 系统配置对象

        Raises:
            APIException: 当某个目录不存在或不是目录时
        """
        dirs_to_check = []
        if config.storage_host_root_dir:
            dirs_to_check.append(("存储宿主机根目录", config.storage_host_root_dir))
        if config.storage_docker_mount_dir:
            dirs_to_check.append(("Docker 挂载目录", config.storage_docker_mount_dir))

        for label, path_str in dirs_to_check:
            path = Path(path_str).expanduser()
            if not path.exists():
                raise APIException(f"{label} 不存在: {path_str}", 400)
            if not path.is_dir():
                raise APIException(f"{label} 不是目录: {path_str}", 400)


# 全局服务单例
system_config_service = SystemConfigService()
