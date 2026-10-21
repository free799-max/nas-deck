"""qBittorrent 应用客户端实现。"""

import asyncio
import json
import logging
import re
import time
from urllib.parse import urlparse

import httpx

from app.services.apps.base import (
    AppClient,
    AuthVerifyResult,
    LogsReader,
    ProvisionResult,
)
from app.services.apps.qbittorrent.inspection import QBittorrentInspectionMixin
from app.services.apps.registry import register_client

logger = logging.getLogger(__name__)

# qBittorrent >= 4.6.1 未设密码时首次启动在日志输出临时密码（按界面语言可能是中文）
_TEMP_PASSWORD_PATTERN = re.compile(
    r"temporary password is provided for this session:\s*(\S+)"
    r"|临时密码[：:]\s*(\S+)"
)


class QBittorrentClient(QBittorrentInspectionMixin, AppClient):
    """qBittorrent 应用客户端。"""

    name = "qbittorrent"
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
    ) -> ProvisionResult:
        """把统一账号密码配置进 qBittorrent 并复验。

        qBittorrent 5.x 首次启动未设密码时会在日志输出临时密码：
        解析临时密码（兜底尝试旧默认 adminadmin）登录后，
        通过 setPreferences 修改为目标账号密码，再用新凭据登录复验。

        Docker 端口映射场景下 Host 头端口与 WebUI 监听端口不一致，
        会触发 Host 头校验拒绝请求（全站 401）：此时按容器内监听端口
        伪装 Host/Referer 完成配置，并顺带关闭 Host 头校验，
        保证用户浏览器直连宿主端口也能正常访问。
        """
        base_url = str(url or "").rstrip("/")
        if not base_url:
            return ProvisionResult(ok=False, message="访问地址不能为空")

        parsed = urlparse(base_url)
        plain_headers = {"Referer": base_url}
        if host_header_port:
            authority = f"{parsed.hostname}:{host_header_port}"
            login_headers = {
                "Host": authority,
                "Referer": f"{parsed.scheme}://{authority}",
            }
        else:
            login_headers = plain_headers

        deadline = time.monotonic() + self.PROVISION_TIMEOUT
        last_error = "服务未就绪"

        while time.monotonic() < deadline:
            try:
                async with httpx.AsyncClient(
                    timeout=self.TIMEOUT,
                    follow_redirects=True,
                ) as client:
                    # 目标凭据已生效（重复执行/已配置过）则直接成功
                    if await self._try_login(
                        client, base_url, username, password, headers=plain_headers
                    ):
                        return ProvisionResult(ok=True, message="账号已配置并验证通过")

                    candidates: list[tuple[str, str]] = []
                    if logs_reader is not None:
                        try:
                            logs = await logs_reader()
                        except Exception as exc:
                            logger.warning("读取 qBittorrent 容器日志失败: %s", exc)
                            logs = ""
                        for match in _TEMP_PASSWORD_PATTERN.findall(logs):
                            # 多语言正则分组：findall 返回元组，取第一个非空分组
                            candidates.extend(
                                ("admin", g) for g in match if g
                            )
                    # 配置卷复用（修复）时无临时密码输出，旧密码仍有效
                    if previous_password:
                        candidates.append((username, previous_password))
                    candidates.append(("admin", "adminadmin"))

                    last_error = "等待服务就绪或临时密码输出"
                    for login_username, candidate in dict.fromkeys(candidates):
                        if login_username == username and candidate == password:
                            continue
                        if not await self._try_login(
                            client,
                            base_url,
                            login_username,
                            candidate,
                            headers=login_headers,
                        ):
                            continue
                        preferences = {
                            "web_ui_username": username,
                            "web_ui_password": password,
                        }
                        if host_header_port:
                            # 关闭 Host 头校验，否则外部经映射端口访问会被 401
                            preferences["web_ui_host_header_validation_enabled"] = False
                        resp = await client.post(
                            f"{base_url}/api/v2/app/setPreferences",
                            data={"json": json.dumps(preferences)},
                            headers=login_headers,
                        )
                        if resp.status_code in (401, 403):
                            last_error = "修改密码请求被拒绝"
                            break
                        resp.raise_for_status()
                        # Host 头校验已关闭，按用户实际访问方式复验
                        if await self._try_login(
                            client, base_url, username, password, headers=plain_headers
                        ):
                            return ProvisionResult(ok=True, message="账号已配置并验证通过")
                        last_error = "密码已提交但新凭据验证失败"
                        break
            except httpx.RequestError as exc:
                last_error = f"无法连接到应用: {exc}"
            await asyncio.sleep(5)

        return ProvisionResult(ok=False, message=f"自动配置超时: {last_error}")

    async def _try_login(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        username: str,
        password: str,
        headers: dict | None = None,
    ) -> bool:
        """尝试登录，成功后会话 Cookie 保留在 client 中。"""
        try:
            resp = await client.post(
                f"{base_url}/api/v2/auth/login",
                data={"username": username, "password": password},
                headers=headers or {"Referer": base_url},
            )
        except httpx.RequestError:
            raise
        if resp.status_code in (401, 403):
            # 多次失败会被 qBittorrent 封禁 IP；Host 头校验不通过也是 401
            logger.warning(
                "qBittorrent 登录被拒绝(%s): %s", resp.status_code, resp.text[:120]
            )
            return False
        text = resp.text.strip().lower()
        return resp.status_code == 204 or text in ("ok.", "ok")

    async def verify_auth(self, config: dict) -> AuthVerifyResult:
        """校验 qBittorrent 访问地址与认证配置。"""
        base_url = str(config.get("url") or "").rstrip("/")
        if not base_url:
            return AuthVerifyResult(valid=False, message="访问地址不能为空")

        auth_type = config.get("auth_type") or "none"

        try:
            if auth_type == "api_key":
                return await self._verify_api_key(
                    base_url,
                    config.get("api_key", ""),
                )
            if auth_type == "basic":
                return await self._verify_basic(
                    base_url,
                    config.get("username", ""),
                    config.get("password", ""),
                )
            return AuthVerifyResult(valid=False, message="qBittorrent 必须选择认证方式")
        except httpx.TimeoutException:
            return AuthVerifyResult(valid=False, message="连接超时，请检查地址与网络")
        except httpx.RequestError as exc:
            return AuthVerifyResult(valid=False, message=f"无法连接到应用: {exc}")

    async def _verify_basic(
        self,
        base_url: str,
        username: str,
        password: str,
    ) -> AuthVerifyResult:
        """使用用户名/密码登录后校验会话是否有效。"""
        if not username or not password:
            return AuthVerifyResult(valid=False, message="用户名和密码不能为空")

        # qBittorrent 启用 CSRF 保护时，要求 Referer/Origin 与访问地址匹配
        csrf_headers = {"Referer": base_url}

        async with httpx.AsyncClient(
            timeout=self.TIMEOUT,
            follow_redirects=True,
        ) as client:
            login_resp = await client.post(
                f"{base_url}/api/v2/auth/login",
                data={"username": username, "password": password},
                headers=csrf_headers,
            )

            if login_resp.status_code in (401, 403):
                return AuthVerifyResult(
                    valid=False,
                    message="认证被拒绝，请检查用户名/密码；如启用了 CSRF 保护，请确认访问地址与 Referer 一致",
                )

            # qBittorrent 登录接口：旧版返回 200 + "Ok."，新版（如 5.x）返回 204 + Set-Cookie
            resp_text = login_resp.text.strip()
            login_ok = (
                login_resp.status_code == 204
                or resp_text.lower() in ("ok.", "ok")
            )
            if not login_ok:
                logger.warning(
                    "qBittorrent %s auth/login 响应非预期: status=%s body=%r",
                    base_url,
                    login_resp.status_code,
                    resp_text[:200],
                )
                # 避免消息过长或泄露敏感信息，仅展示前 80 字符
                preview = resp_text[:80] or "空响应"
                return AuthVerifyResult(
                    valid=False,
                    message=f"用户名或密码错误（qBittorrent 返回: {preview}）",
                )

            version_resp = await client.get(
                f"{base_url}/api/v2/app/version",
                headers=csrf_headers,
            )
            if version_resp.status_code in (401, 403):
                return AuthVerifyResult(valid=False, message="登录后权限校验失败")
            version_resp.raise_for_status()
            return AuthVerifyResult(valid=True, message="用户名/密码认证成功")

    async def _verify_api_key(self, base_url: str, api_key: str) -> AuthVerifyResult:
        """使用 API Key（v5.2.0+）校验。"""
        if not api_key:
            return AuthVerifyResult(valid=False, message="API Key 不能为空")

        # 同样携带 Referer，避免 CSRF 保护拦截
        csrf_headers = {"Referer": base_url}

        async with httpx.AsyncClient(
            timeout=self.TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                f"{base_url}/api/v2/app/version",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    **csrf_headers,
                },
            )
            if response.status_code in (401, 403):
                return AuthVerifyResult(valid=False, message="API Key 认证失败")
            response.raise_for_status()
            return AuthVerifyResult(valid=True, message="API Key 认证成功")


register_client(QBittorrentClient.name, QBittorrentClient)
