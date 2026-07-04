"""qBittorrent 应用客户端实现。"""

import logging

import httpx

from app.services.apps.base import AppClient, AuthVerifyResult
from app.services.apps.registry import register_client

logger = logging.getLogger(__name__)


class QBittorrentClient(AppClient):
    """qBittorrent 应用客户端。"""

    name = "qbittorrent"
    TIMEOUT = 10.0

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
