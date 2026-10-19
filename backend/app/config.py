"""应用配置模块。

使用 pydantic-settings 从环境变量或 .env 文件加载配置，
所有配置项均有默认值，可通过环境变量覆盖。
"""

import os

from pydantic import model_validator
from pydantic_settings import BaseSettings

# SECRET_KEY 的默认占位值，启动时检测到该值会自动生成随机密钥
DEFAULT_SECRET_KEY = "change-me-in-production"


class Settings(BaseSettings):
    """全局应用配置。"""

    APP_NAME: str = "NasDeck"
    """应用名称。"""

    DATABASE_URL: str = "postgresql+asyncpg://nasdeck:nasdeck@localhost:5434/nasdeck"
    """数据库连接字符串，默认使用本机 Docker PostgreSQL 异步驱动。"""

    SECRET_KEY: str = DEFAULT_SECRET_KEY
    """JWT 签名密钥，生产环境必须替换为随机字符串。"""

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    """访问令牌过期时间（分钟），默认 24 小时。"""

    REGISTRATION_OPEN: bool = False
    """是否开放新用户注册。首个用户始终允许注册并成为管理员。"""

    CORS_ORIGINS: str = "http://localhost:5173"
    """允许的跨域来源，逗号分隔。"""

    DATA_ROOT: str = "./data"
    """数据根目录，Compose 工作区与应用图标默认存放于其下。"""

    COMPOSE_WORKSPACE_DIR: str = ""
    """Compose 项目工作目录，默认为 DATA_ROOT/compose，可单独覆盖。"""

    APP_ICON_DIR: str = ""
    """用户上传的应用商店图标存储目录，默认为 DATA_ROOT/app-icons，可单独覆盖。"""

    @model_validator(mode="after")
    def _fill_data_subdirs(self) -> "Settings":
        """未显式配置时，将子目录默认值填充到 DATA_ROOT 之下。"""
        if not self.COMPOSE_WORKSPACE_DIR:
            self.COMPOSE_WORKSPACE_DIR = os.path.join(self.DATA_ROOT, "compose")
        if not self.APP_ICON_DIR:
            self.APP_ICON_DIR = os.path.join(self.DATA_ROOT, "app-icons")
        return self

    def cors_origin_list(self) -> list[str]:
        """解析 CORS_ORIGINS 为来源列表。"""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = {"env_file": ".env"}
    """指定 .env 文件路径用于加载环境变量。"""


# 全局配置单例
settings = Settings()
