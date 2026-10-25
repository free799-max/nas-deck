"""音乐自动整理配置相关 Schema。"""

from pydantic import BaseModel, Field


class MusicAutoDirItem(BaseModel):
    """整理目录层级的一项（如 artist / album）。"""

    value: str = ""
    value2: str = ""


class MusicAutoOrganizeConfigIn(BaseModel):
    """自动整理配置请求。

    所有字段都可省略，由后端按默认值补齐；目录为 Music Tag Web
    容器内路径，与自动化页应用配置保持一致。
    """

    enabled: bool = False
    interval_minutes: int = Field(5, ge=1, le=1440)
    watch_dir: str = "/app/media/downloads"
    library_dir: str = "/app/media/music"
    scrape_enabled: bool = True
    tidy_enabled: bool = True
    source_list: list[str] = Field(default_factory=list)
    modify_list: list[str] = Field(default_factory=list)
    dir_list: list[MusicAutoDirItem] = Field(default_factory=list)
    min_age_seconds: int = Field(60, ge=0, le=86400)
    max_files_per_run: int = Field(20, ge=1, le=200)
    scrape_timeout_seconds: int = Field(180, ge=10, le=3600)
    tidy_timeout_seconds: int = Field(180, ge=10, le=3600)
    navidrome_scan: bool = True
    select_mode: str = "hard"
    skip_tag: bool = False
    folder_album: bool = False
