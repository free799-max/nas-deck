"""应用客户端抽象基类与通用模型。"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


@dataclass
class AuthVerifyResult:
    """应用认证检测结果。"""

    valid: bool
    message: str | None = None


@dataclass
class ProvisionResult:
    """应用自动配置（写入账号密码/API Key）结果。"""

    ok: bool
    message: str | None = None
    api_key: str | None = None


@dataclass
class InspectItem:
    """应用配置健康检测项。"""

    id: str
    title: str
    # 检测结论：ok / warn / error
    status: str
    message: str | None = None
    current_value: str | None = None
    expected_value: str | None = None
    # 是否支持通过 apply_fix 自动修复
    fixable: bool = False
    # 前端展示分组（可选），如“核心配置”
    category: str | None = None


@dataclass
class InspectReport:
    """应用配置健康检测报告。"""

    supported: bool
    items: list[InspectItem] = field(default_factory=list)


@dataclass
class FixResultItem:
    """单个检测项的自动修复结果。"""

    id: str
    ok: bool
    message: str | None = None


# 读取容器日志的异步回调，由调度方注入（避免客户端依赖 docker SDK）
LogsReader = Callable[[], Awaitable[str]]


class AppClientError(Exception):
    """应用客户端内部异常。"""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class AppClient(ABC):
    """应用专属客户端抽象基类。

    每个受支持的应用都应实现一个子类，并注册到 registry 中。
    子类除 ``verify_auth`` 外，还可以按需扩展站点、订阅、下载等接口。
    """

    name: str

    #: 是否支持部署后自动配置账号密码/API Key
    supports_provision: bool = False

    @abstractmethod
    async def verify_auth(self, config: dict) -> AuthVerifyResult:
        """校验应用访问地址与认证信息是否有效。"""
        ...

    async def provision(
        self,
        url: str,
        username: str,
        password: str,
        api_key: str | None = None,
        logs_reader: LogsReader | None = None,
        previous_password: str | None = None,
        host_header_port: int | None = None,
    ) -> ProvisionResult:
        """把统一账号密码/API Key 配置进真实服务并复验。

        Args:
            url: 应用访问地址
            username: 目标管理员用户名
            password: 目标管理员密码
            api_key: 预生成的 API Key（env 注入类应用使用）
            logs_reader: 读取容器日志的异步回调（需要解析初始密码的应用使用）
            previous_password: 修复场景下服务当前的旧密码（env 注入类应用
                的密码仅在首次初始化生效，需用旧密码登录后改密）
            host_header_port: 容器内 WebUI 监听端口。Docker 端口映射导致
                Host 头端口与监听端口不一致时，qBittorrent 5.x 的 Host 头
                校验会拒绝请求，需按此端口伪装 Host/Referer 头
        """
        return ProvisionResult(ok=False, message="该应用不支持自动配置")

    async def inspect(self, ctx: dict) -> InspectReport:
        """检测应用配置健康度（默认不支持）。

        Args:
            ctx: 检测上下文。基础键为 ``url``/``username``/``password``/``api_key``；
                调度方按需注入扩展键：``logs_reader``（读容器日志回调）、
                ``host_header_port``（容器内 WebUI 端口）、``container_name``
                （Compose 主容器名）、``shared_config``（编排共享配置）、
                ``integrations``（该应用 app_configs 里的装配结果）、
                ``expected_listen_port``（期望的容器内监听端口）、
                ``save_app_config``（把检测/修复结果回写 app_configs 的异步回调）、
                ``wire``（重跑所在组自动装配的异步回调）
        """
        return InspectReport(supported=False, items=[])

    async def apply_fix(self, ctx: dict, item_ids: list[str]) -> list[FixResultItem]:
        """自动修复指定检测项（默认不支持）。

        Args:
            ctx: 与 ``inspect`` 相同的检测上下文
            item_ids: 待修复的检测项 ID 列表
        """
        return [
            FixResultItem(id=item_id, ok=False, message="该应用不支持自动修复")
            for item_id in item_ids
        ]
