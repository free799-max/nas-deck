"""系统全局配置服务。

提供系统配置的获取、初始化和更新能力。
整个系统只维护一条配置记录（id=1）。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_config import SystemConfig
from app.schemas.system_config import SystemConfigUpdate


class SystemConfigService:
    """系统全局配置服务。"""

    async def get_or_create(self, db: AsyncSession) -> SystemConfig:
        """获取系统配置，不存在则创建默认记录。

        Args:
            db: 异步数据库会话

        Returns:
            SystemConfig: 系统配置对象
        """
        result = await db.execute(select(SystemConfig).where(SystemConfig.id == 1))
        config = result.scalar_one_or_none()
        if config is None:
            config = SystemConfig(id=1)
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
            dict: 包含 id、代理配置、端口分配与管理员工凭据的字典
        """
        return {
            "id": config.id,
            "http_proxy": config.http_proxy,
            "https_proxy": config.https_proxy,
            "no_proxy": config.no_proxy,
            "service_port_start": config.service_port_start,
            "default_admin_username": config.default_admin_username,
            "default_admin_password": config.default_admin_password,
        }


# 全局服务单例
system_config_service = SystemConfigService()
