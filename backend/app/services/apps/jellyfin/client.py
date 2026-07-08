"""Jellyfin 应用客户端实现。"""

import json

import httpx

from app.services.apps.base import AppClient, AuthVerifyResult
from app.services.apps.registry import register_client


class JellyfinClient(AppClient):
    """Jellyfin 应用客户端。"""

    name = "jellyfin"
    TIMEOUT = 10.0

    # Jellyfin/Emby 统一要求的设备信息头
    _AUTHORIZATION_HEADER = (
        'MediaBrowser Client="NasDeck", Device="NAS", DeviceId="nasdeck", Version="1.0.0"'
    )

    async def verify_auth(self, config: dict) -> AuthVerifyResult:
        """校验 Jellyfin 访问地址与认证配置。"""
        base_url = str(config.get("url") or "").rstrip("/")
        if not base_url:
            return AuthVerifyResult(valid=False, message="访问地址不能为空")

        auth_type = config.get("auth_type") or "none"

        try:
            if auth_type == "api_key":
                return await self._verify_api_key(base_url, config.get("api_key", ""))
            if auth_type == "basic":
                return await self._verify_basic(
                    base_url,
                    config.get("username", ""),
                    config.get("password", ""),
                )
            return await self._verify_none(base_url)
        except httpx.TimeoutException:
            return AuthVerifyResult(valid=False, message="连接超时，请检查地址与网络")
        except httpx.RequestError as exc:
            return AuthVerifyResult(valid=False, message=f"无法连接到应用: {exc}")

    async def _verify_api_key(self, base_url: str, api_key: str) -> AuthVerifyResult:
        """使用 API Key 验证。"""
        if not api_key:
            return AuthVerifyResult(valid=False, message="API Key 不能为空")

        async with httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=True) as client:
            response = await client.get(
                f"{base_url}/System/Info",
                headers={
                    "X-Emby-Token": api_key,
                    "Authorization": self._AUTHORIZATION_HEADER,
                },
            )
            if response.status_code in (401, 403):
                return AuthVerifyResult(valid=False, message="API Key 认证失败")
            response.raise_for_status()
            return AuthVerifyResult(valid=True, message="API Key 认证成功")

    async def _verify_basic(
        self,
        base_url: str,
        username: str,
        password: str,
    ) -> AuthVerifyResult:
        """使用用户名/密码验证。"""
        if not username or not password:
            return AuthVerifyResult(valid=False, message="用户名和密码不能为空")

        async with httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=True) as client:
            login_resp = await client.post(
                f"{base_url}/Users/AuthenticateByName",
                headers={"Authorization": self._AUTHORIZATION_HEADER},
                json={"Username": username, "Pw": password},
            )
            if login_resp.status_code in (401, 403):
                return AuthVerifyResult(valid=False, message="用户名或密码错误")
            login_resp.raise_for_status()

            try:
                login_data = login_resp.json()
            except json.JSONDecodeError:
                return AuthVerifyResult(valid=False, message="登录接口返回异常")

            access_token = login_data.get("AccessToken")
            if not access_token:
                return AuthVerifyResult(valid=False, message="登录接口未返回 Token")

            info_resp = await client.get(
                f"{base_url}/System/Info",
                headers={
                    "X-Emby-Token": access_token,
                    "Authorization": self._AUTHORIZATION_HEADER,
                },
            )
            if info_resp.status_code in (401, 403):
                return AuthVerifyResult(valid=False, message="Token 验证失败")
            info_resp.raise_for_status()
            return AuthVerifyResult(valid=True, message="用户名/密码认证成功")

    async def _verify_none(self, base_url: str) -> AuthVerifyResult:
        """无认证时仅确认应用可达。"""
        async with httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=True) as client:
            response = await client.get(f"{base_url}/System/Info/Public")
            response.raise_for_status()
            return AuthVerifyResult(valid=True, message="应用可正常访问")


register_client(JellyfinClient.name, JellyfinClient)
