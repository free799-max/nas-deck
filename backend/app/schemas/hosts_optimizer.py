"""Hosts 优选相关 Pydantic Schema。"""

from typing import Any, Literal

from pydantic import BaseModel, Field

DEFAULT_HOSTS_OPTIMIZER_DOMAINS = [
    "api.themoviedb.org",
    "www.themoviedb.org",
    "image.tmdb.org",
    "api.tmdb.org",
    "themoviedb.org",
    "github.com",
    "api.github.com",
    "objects.githubusercontent.com",
    "codeload.github.com",
]
"""默认参与优选的域名。"""

DEFAULT_HOSTS_OPTIMIZER_INTERVAL_MINUTES = 360
"""自动模式默认间隔（6 小时）。"""

DEFAULT_HOSTS_OPTIMIZER_TOP_N = 2
"""每个域名默认保留的 IP 数量。"""


class HostsOptimizerConfig(BaseModel):
    """Hosts 优选配置。"""

    enabled: bool = Field(False, description="是否启用")
    mode: Literal["manual", "auto"] = Field("manual", description="manual 仅手动 / auto 定时")
    interval_minutes: int = Field(
        DEFAULT_HOSTS_OPTIMIZER_INTERVAL_MINUTES,
        ge=5,
        le=10080,
        description="自动模式运行间隔（分钟）",
    )
    top_n: int = Field(
        DEFAULT_HOSTS_OPTIMIZER_TOP_N,
        ge=1,
        le=5,
        description="每个域名保留的 IP 数量",
    )
    domains: list[str] = Field(
        default_factory=lambda: list(DEFAULT_HOSTS_OPTIMIZER_DOMAINS),
        description="参与优选的域名",
    )
    adguard_url: str | None = Field(None, max_length=500, description="AdGuard Home 管理地址")
    adguard_username: str = Field("admin", max_length=255, description="AdGuard 管理员用户名")
    adguard_password: str = Field("", max_length=255, description="AdGuard 管理员密码")


class HostsOptimizerConfigUpdate(HostsOptimizerConfig):
    """更新 Hosts 优选配置（整份提交，便于区分清空与未提交）。"""


class HostsOptimizerTestRequest(BaseModel):
    """测试 AdGuard 连接。字段为空时使用已保存的配置。"""

    adguard_url: str | None = Field(None, max_length=500)
    adguard_username: str | None = Field(None, max_length=255)
    adguard_password: str | None = Field(None, max_length=255)


class HostsOptimizerTestResult(BaseModel):
    """AdGuard 连接测试结果。"""

    ok: bool
    version: str | None = None
    message: str = ""


class HostsOptimizerStatusOut(BaseModel):
    """Hosts 优选运行状态。"""

    running: bool = False
    next_run_at: str | None = None
    last_run: dict[str, Any] | None = None


class HostsOptimizerRunOut(BaseModel):
    """一次优选的结果。"""

    mode: str
    started_at: str
    finished_at: str | None = None
    duration_ms: int = 0
    adguard: str = "ok"
    errors: list[str] = Field(default_factory=list)
    domains: dict[str, Any] = Field(default_factory=dict)
