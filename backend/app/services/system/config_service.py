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
            if docker_path.is_dir():
                return host_root, docker_mount
            # 回退到 host_root/docker（允许目录不存在，后续部署时自动创建）
            fallback = host_path / "docker"
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

        if data.service_port_start is not None:
            config.service_port_start = data.service_port_start

        if data.default_admin_username is not None:
            username = data.default_admin_username.strip()
            config.default_admin_username = username or "admin"
        if data.default_admin_password is not None:
            config.default_admin_password = data.default_admin_password.strip()

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
            "service_port_start": config.service_port_start,
            "default_admin_username": config.default_admin_username,
            "default_admin_password": config.default_admin_password,
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
