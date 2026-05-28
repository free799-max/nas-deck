"""应用配置模块。

使用 pydantic-settings 从环境变量或 .env 文件加载配置，
所有配置项均有默认值，可通过环境变量覆盖。
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局应用配置。"""

    APP_NAME: str = "NasDeck"
    """应用名称。"""

    DATABASE_URL: str = "sqlite+aiosqlite:///./nasdeck.db"
    """数据库连接字符串，默认使用本地 SQLite 异步驱动。"""

    SECRET_KEY: str = "change-me-in-production"
    """JWT 签名密钥，生产环境必须替换为随机字符串。"""

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    """访问令牌过期时间（分钟），默认 24 小时。"""

    PLUGIN_DIR: str = "app/plugins"
    """插件自动发现目录。"""

    model_config = {"env_file": ".env"}
    """指定 .env 文件路径用于加载环境变量。"""


# 全局配置单例
settings = Settings()
