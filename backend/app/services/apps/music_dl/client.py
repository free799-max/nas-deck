"""music-dl（Go Music DL）应用客户端实现。

music-dl 首次打开系统配置前需要初始化管理员账号：启动日志输出一次性
``Web setup token``，通过 ``POST /music/setup`` 创建本地管理员后，后续
配置接口使用 ``music_dl_session`` 会话 Cookie。部署后自动配置流程据此
创建管理员（或直接登录已有管理员），并把下载目录改为编排共享目录。
"""

import asyncio
import json
import re
import time

import httpx

from app.services.apps.base import (
    AppClient,
    AuthVerifyResult,
    LogsReader,
    ProvisionResult,
)
from app.services.apps.registry import register_client

# 首次启动日志中的一次性初始化令牌
_SETUP_TOKEN_PATTERN = re.compile(r"Web setup token:\s*(\S+)")
_AUTH_ERROR_PATTERN = re.compile(
    r'<div class="[^"]*auth-error[^"]*">(.*?)</div>', re.DOTALL
)
# 登录失败次数过多时页面提示的等待秒数
_LOCKOUT_PATTERN = re.compile(r"请\s*(\d+)\s*秒后重试")


def _api_base(url: str) -> str:
    """把应用访问地址转换为 music-dl 路由前缀（默认 ``/music``）。"""
    base = str(url or "").strip().rstrip("/")
    if not base:
        return ""
    if base.endswith("/music"):
        return base
    return f"{base}/music"


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value or "").strip()


class MusicDLClient(AppClient):
    """Go Music DL 全网音乐搜索与下载客户端。"""

    name = "music-dl"
    TIMEOUT = 10.0
    PROVISION_TIMEOUT = 300.0
    supports_provision = True

    async def provision(
        self,
        url: str,
        username: str,
        password: str,
        api_key: str | None = None,
        logs_reader: LogsReader | None = None,
        previous_password: str | None = None,
        host_header_port: int | None = None,
        download_dir: str | None = None,
    ) -> ProvisionResult:
        """创建/登录管理员并写入下载目录。

        首次启动从容器日志解析初始化令牌创建管理员；已初始化时直接登录。
        music-dl 没有改密接口，配置卷复用时若统一密码与旧密码不一致，
        会返回明确的失败提示，避免反复触发登录锁定。
        """
        api = _api_base(url)
        if not api:
            return ProvisionResult(ok=False, message="访问地址不能为空")

        deadline = time.monotonic() + self.PROVISION_TIMEOUT
        last_error = "服务未就绪"

        while time.monotonic() < deadline:
            try:
                async with httpx.AsyncClient(
                    timeout=self.TIMEOUT,
                    follow_redirects=True,
                ) as client:
                    settings = await client.get(f"{api}/settings")
                    if settings.status_code != 200:
                        last_error = (
                            f"服务响应异常: HTTP {settings.status_code}"
                        )
                        await asyncio.sleep(5)
                        continue

                    status, _ = await self._auth_status(client, api)
                    if status == "ready":
                        pass
                    elif status == "setup":
                        token = await self._read_setup_token(logs_reader)
                        if not token:
                            last_error = "等待服务输出初始化令牌"
                            await asyncio.sleep(5)
                            continue
                        ok, error = await self._setup_admin(
                            client, api, token, username, password
                        )
                        if not ok:
                            return ProvisionResult(
                                ok=False,
                                message=f"初始化管理员失败: {error}",
                            )
                    else:
                        if previous_password and previous_password != password:
                            # 先验证配置卷里的旧密码：能登录说明服务已初始化
                            # 且统一密码尚未生效（music-dl 无改密接口）。
                            old_ok, old_error = await self._login(
                                client,
                                api,
                                username,
                                previous_password,
                            )
                            if old_ok:
                                return ProvisionResult(
                                    ok=False,
                                    message=(
                                        "服务已有管理员且密码与统一密码不一致，"
                                        "请手动重置密码或重新部署数据卷"
                                    ),
                                )
                            # 失败会触发 music-dl 的登录锁定，等锁定结束后
                            # 再用目标密码验证一次
                            await self._wait_login_lockout(old_error)

                        ok, error = await self._login(
                            client, api, username, password
                        )
                        if not ok:
                            return ProvisionResult(
                                ok=False,
                                message=f"登录失败: {error}",
                            )

                    dir_error = None
                    if download_dir:
                        ok, dir_error = await self._apply_download_dir(
                            client, api, download_dir
                        )
                        if not ok:
                            return ProvisionResult(
                                ok=False,
                                message=(
                                    "账号已配置，但下载目录配置失败: "
                                    f"{dir_error}"
                                ),
                            )

                    message = "账号已配置并验证通过"
                    if download_dir:
                        message = f"{message}，下载目录 {download_dir}"
                    return ProvisionResult(
                        ok=True,
                        message=message,
                        username=username,
                        download_dir=download_dir or None,
                    )
            except httpx.RequestError as exc:
                last_error = f"无法连接到应用: {exc}"
            await asyncio.sleep(5)

        return ProvisionResult(ok=False, message=f"自动配置超时: {last_error}")

    async def verify_auth(self, config: dict) -> AuthVerifyResult:
        """校验 music-dl 访问地址与账号密码。"""
        api = _api_base(str(config.get("url") or ""))
        if not api:
            return AuthVerifyResult(valid=False, message="访问地址不能为空")

        auth_type = config.get("auth_type") or "none"
        if auth_type in ("api_key", "apikey"):
            return AuthVerifyResult(
                valid=False, message="music-dl 不支持 API Key，请使用账号密码"
            )
        if auth_type != "basic":
            return AuthVerifyResult(
                valid=False, message="music-dl 需要账号密码认证"
            )

        username = str(config.get("username") or "")
        password = str(config.get("password") or "")
        if not username or not password:
            return AuthVerifyResult(
                valid=False, message="用户名和密码不能为空"
            )

        try:
            async with httpx.AsyncClient(
                timeout=self.TIMEOUT,
                follow_redirects=True,
            ) as client:
                ok, error = await self._login(client, api, username, password)
                if ok:
                    return AuthVerifyResult(valid=True, message="登录成功")
                return AuthVerifyResult(
                    valid=False, message=error or "登录失败"
                )
        except httpx.TimeoutException:
            return AuthVerifyResult(
                valid=False, message="连接超时，请检查地址与网络"
            )
        except httpx.RequestError as exc:
            return AuthVerifyResult(
                valid=False, message=f"无法连接到应用: {exc}"
            )

    @staticmethod
    async def _auth_status(
        client: httpx.AsyncClient, api: str
    ) -> tuple[str, dict]:
        """读取认证状态：已登录 ready / 需初始化 setup / 需登录 login。"""
        resp = await client.get(
            f"{api}/cookies", headers={"Accept": "application/json"}
        )
        if resp.status_code == 200:
            return "ready", {}
        try:
            payload = resp.json()
        except (json.JSONDecodeError, ValueError):
            return "login", {}
        if isinstance(payload, dict) and payload.get("setupRequired"):
            return "setup", payload
        return "login", payload if isinstance(payload, dict) else {}

    @staticmethod
    async def _read_setup_token(logs_reader: LogsReader | None) -> str | None:
        if logs_reader is None:
            return None
        try:
            logs = await logs_reader()
        except Exception:
            return None
        matches = _SETUP_TOKEN_PATTERN.findall(logs or "")
        return matches[-1] if matches else None

    async def _setup_admin(
        self,
        client: httpx.AsyncClient,
        api: str,
        token: str,
        username: str,
        password: str,
    ) -> tuple[bool, str | None]:
        """用一次性令牌创建管理员并校验会话。"""
        resp = await client.post(
            f"{api}/setup",
            data={
                "setup_token": token,
                "username": username,
                "password": password,
                "password_confirm": password,
                "next": "/music/",
            },
        )
        verify = await client.get(
            f"{api}/cookies", headers={"Accept": "application/json"}
        )
        if verify.status_code == 200:
            return True, None
        return False, self._extract_error(resp) or "创建管理员后会话无效"

    async def _login(
        self,
        client: httpx.AsyncClient,
        api: str,
        username: str,
        password: str,
    ) -> tuple[bool, str | None]:
        """登录并校验会话 Cookie 是否生效。"""
        resp = await client.post(
            f"{api}/login",
            data={"username": username, "password": password, "next": "/music/"},
            follow_redirects=False,
        )
        if resp.status_code in (301, 302, 303, 307, 308):
            verify = await client.get(
                f"{api}/cookies", headers={"Accept": "application/json"}
            )
            if verify.status_code == 200:
                return True, None
            return False, "登录后会话未生效"
        if resp.status_code == 200:
            return False, self._extract_error(resp) or "用户名或密码不正确"
        return False, f"登录接口异常: HTTP {resp.status_code}"

    @staticmethod
    async def _wait_login_lockout(error: str | None) -> None:
        """登录失败后的锁定等待，避免下一次验证被锁定拦截。"""
        match = _LOCKOUT_PATTERN.search(error or "")
        if match:
            delay = min(int(match.group(1)) + 1, 61)
        elif error:
            delay = 2
        else:
            return
        await asyncio.sleep(delay)

    async def _apply_download_dir(
        self,
        client: httpx.AsyncClient,
        api: str,
        download_dir: str,
    ) -> tuple[bool, str | None]:
        """把下载目录写入 music-dl 系统设置并复验。"""
        resp = await client.get(f"{api}/settings")
        if resp.status_code != 200:
            return False, f"读取系统设置失败: HTTP {resp.status_code}"
        try:
            settings = resp.json()
        except (json.JSONDecodeError, ValueError):
            return False, "系统设置返回异常"
        if not isinstance(settings, dict):
            return False, "系统设置返回异常"
        if settings.get("downloadDir") == download_dir:
            return True, None

        settings["downloadDir"] = download_dir
        saved = await client.post(f"{api}/settings", json=settings)
        if saved.status_code >= 400:
            return False, self._extract_error(saved) or (
                f"保存系统设置失败: HTTP {saved.status_code}"
            )
        try:
            payload = saved.json()
        except (json.JSONDecodeError, ValueError):
            return False, "保存系统设置返回异常"
        if not isinstance(payload, dict) or payload.get("downloadDir") != download_dir:
            return False, "下载目录未生效"
        return True, None

    @staticmethod
    def _extract_error(resp: httpx.Response) -> str | None:
        """从登录/初始化 HTML 页面或 JSON 错误响应中提取提示。"""
        try:
            payload = resp.json()
        except (json.JSONDecodeError, ValueError):
            payload = None
        if isinstance(payload, dict) and payload.get("error"):
            return str(payload["error"])
        match = _AUTH_ERROR_PATTERN.search(resp.text or "")
        if match:
            return _strip_html(match.group(1)) or None
        return None


register_client(MusicDLClient.name, MusicDLClient)
