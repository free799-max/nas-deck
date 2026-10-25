"""Reader 自动同步配置相关 Schema。"""

from pydantic import BaseModel, Field


class ReaderAutoSyncConfigIn(BaseModel):
    """Reader 书架自动导出与二毛书库扫描配置。

    所有字段都可省略，由后端按默认值补齐；目录同时保留 Reader 容器内
    路径与后端可写的宿主机路径，界面上可从应用实际挂载一键填充。
    """

    enabled: bool = False
    interval_minutes: int = Field(10, ge=1, le=1440)

    reader_url: str = ""
    reader_username: str = ""
    reader_password: str = ""
    reader_token: str = ""

    # Reader 容器内的书库目录与对应的宿主机目录
    library_dir: str = ""
    library_host_dir: str = ""
    # 二毛容器内同一书库的目录（用于自动创建/匹配书库）
    ermao_library_dir: str = ""

    cache_missing_chapters: bool = True
    max_seconds: int = Field(2700, ge=60, le=21600)

    scan_enabled: bool = True
    scan_wait_seconds: int = Field(180, ge=10, le=3600)
    auto_setup: bool = True

    ermao_url: str = ""
    ermao_email: str = ""
    ermao_password: str = ""
    ermao_lib_id: str = ""
