"""Comic Auto 应用客户端实现。

Comic Auto 的接口统一返回 ``{"code": 0, "msg": "...", "data": ...}``，
登录接口返回 Django SimpleJWT 结构（``access`` / ``refresh``）。
"""

import asyncio
import json
import time
from typing import Any

import httpx

from app.services.apps.base import (
    AppClient,
    AuthVerifyResult,
    LogsReader,
    ProvisionResult,
)
from app.services.apps.registry import register_client


class ComicAutoClient(AppClient):
    """Comic Auto 漫画订阅与下载客户端。"""

    name = "comic-auto"
    TIMEOUT = 15.0
    PROVISION_TIMEOUT = 300.0
    supports_provision = True
    # 装配时使用管理员账号换取 JWT，不强制依赖 API Key
    requires_api_key = False

    # 共享存储约定的默认目录（与编排模板一致）
    DEFAULT_DOWNLOAD_DIR = "/mnt/media/down"
    DEFAULT_CACHE_DIR = "/mnt/media/cache"

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
        """创建管理员、验证登录并生成 API Key。

        首次启动调用初始化接口创建管理员；重复部署时直接登录复验，
        若统一密码已变更则尝试用旧密码登录后改密。
        """
        base_url = str(url or "").rstrip("/")
        if not base_url:
            return ProvisionResult(ok=False, message="访问地址不能为空")

        deadline = time.monotonic() + self.PROVISION_TIMEOUT
        last_error = "服务未就绪"

        while time.monotonic() < deadline:
            try:
                async with httpx.AsyncClient(
                    timeout=self.TIMEOUT,
                    follow_redirects=True,
                ) as client:
                    await self._ensure_initialized(
                        client, base_url, username, password
                    )

                    token, error = await self._login(
                        client, base_url, username, password
                    )
                    if token is None:
                        if previous_password and previous_password != password:
                            changed = await self._change_password(
                                client,
                                base_url,
                                username,
                                previous_password,
                                password,
                            )
                            if changed:
                                await asyncio.sleep(1)
                                token, error = await self._login(
                                    client, base_url, username, password
                                )
                        if token is None:
                            last_error = error or "登录失败"
                            await asyncio.sleep(5)
                            continue

                    generated_key = await self._ensure_api_key(
                        client, base_url, token
                    )
                    return ProvisionResult(
                        ok=True,
                        message="账号已配置并验证通过",
                        api_key=generated_key,
                        username=username,
                    )
            except httpx.RequestError as exc:
                last_error = f"无法连接到应用: {exc}"
            await asyncio.sleep(5)

        return ProvisionResult(ok=False, message=f"自动配置超时: {last_error}")

    async def _ensure_initialized(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        username: str,
        password: str,
    ) -> None:
        """首次启动时通过初始化接口创建管理员；已初始化则直接返回。"""
        try:
            resp = await client.get(f"{base_url}/api/v1/app/init/status/")
        except httpx.RequestError:
            raise
        if resp.status_code != 200:
            return
        try:
            data, _ = self._unwrap(resp.json())
        except json.JSONDecodeError:
            return
        if not isinstance(data, dict):
            return
        needs_setup = (
            data.get("is_initialized") is False
            or data.get("has_admin") is False
        )
        if not needs_setup:
            return
        await client.post(
            f"{base_url}/api/v1/app/init/setup/",
            json={"username": username, "password": password},
        )

    async def _login(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        username: str,
        password: str,
    ) -> tuple[str | None, str | None]:
        """登录并返回 access token。"""
        resp = await client.post(
            f"{base_url}/api/v1/auth/login/",
            json={"username": username, "password": password},
        )
        if resp.status_code in (401, 403):
            return None, "用户名或密码错误"
        if resp.status_code >= 400:
            return None, f"登录接口异常: HTTP {resp.status_code}"
        try:
            payload = resp.json()
        except json.JSONDecodeError:
            return None, "登录接口返回异常"
        token = payload.get("access")
        if not token:
            return None, "登录接口未返回 Token"
        return token, None

    async def _change_password(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        username: str,
        old_password: str,
        new_password: str,
    ) -> bool:
        """用旧密码登录后修改为目标密码。"""
        token, _ = await self._login(client, base_url, username, old_password)
        if not token:
            return False
        resp = await client.post(
            f"{base_url}/api/v1/app/user/change-password/",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "old_password": old_password,
                "new_password": new_password,
                "confirm_password": new_password,
            },
        )
        if resp.status_code >= 400:
            return False
        try:
            _, error = self._unwrap(resp.json())
        except json.JSONDecodeError:
            return False
        return error is None

    async def _ensure_api_key(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        token: str,
    ) -> str | None:
        """读取或生成 API Key，失败不阻断账号配置。"""
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = await client.get(
                f"{base_url}/api/v1/app/api-keys/", headers=headers
            )
            if resp.status_code == 200:
                data, _ = self._unwrap(resp.json())
                key = self._extract_key(data)
                if key:
                    return key
            resp = await client.post(
                f"{base_url}/api/v1/app/api-keys/reset/", headers=headers
            )
            if resp.status_code == 200:
                data, _ = self._unwrap(resp.json())
                return self._extract_key(data)
        except (httpx.RequestError, json.JSONDecodeError):
            return None
        return None

    @staticmethod
    def _extract_key(data: Any) -> str | None:
        """从 API Key 响应中提取密钥，兼容对象/列表结构。"""
        if isinstance(data, dict):
            key = data.get("key") or data.get("api_key")
            return str(key) if key else None
        if isinstance(data, list):
            for item in data:
                key = ComicAutoClient._extract_key(item)
                if key:
                    return key
        return None

    async def verify_auth(self, config: dict) -> AuthVerifyResult:
        """校验访问地址与认证信息。"""
        base_url = str(config.get("url") or "").rstrip("/")
        if not base_url:
            return AuthVerifyResult(valid=False, message="访问地址不能为空")

        auth_type = config.get("auth_type") or "none"
        try:
            if auth_type == "basic":
                return await self._verify_basic(
                    base_url,
                    config.get("username", ""),
                    config.get("password", ""),
                )
            if auth_type in ("api_key", "apikey"):
                return await self._verify_api_key(
                    base_url, config.get("api_key", "")
                )
            return await self._verify_none(base_url)
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
        if not username or not password:
            return AuthVerifyResult(valid=False, message="用户名和密码不能为空")
        async with httpx.AsyncClient(
            timeout=self.TIMEOUT, follow_redirects=True
        ) as client:
            token, error = await self._login(client, base_url, username, password)
        if token:
            return AuthVerifyResult(valid=True, message="账号密码验证成功")
        return AuthVerifyResult(valid=False, message=error or "账号密码验证失败")

    async def _verify_api_key(
        self,
        base_url: str,
        api_key: str,
    ) -> AuthVerifyResult:
        if not api_key:
            return AuthVerifyResult(valid=False, message="API Key 不能为空")
        # Comic Auto 的 API Key 请求头未在文档中固定，兼容常见形式
        headers_list = [
            {"X-API-Key": api_key},
            {"Authorization": f"Bearer {api_key}"},
            {"Authorization": f"Token {api_key}"},
        ]
        async with httpx.AsyncClient(
            timeout=self.TIMEOUT, follow_redirects=True
        ) as client:
            for headers in headers_list:
                resp = await client.get(
                    f"{base_url}/api/v1/app/user/profile/", headers=headers
                )
                if resp.status_code == 200:
                    return AuthVerifyResult(
                        valid=True, message="API Key 认证成功"
                    )
        return AuthVerifyResult(valid=False, message="API Key 认证失败")

    async def _verify_none(self, base_url: str) -> AuthVerifyResult:
        async with httpx.AsyncClient(
            timeout=self.TIMEOUT, follow_redirects=True
        ) as client:
            resp = await client.get(f"{base_url}/api/v1/app/init/status/")
        if resp.status_code == 200:
            return AuthVerifyResult(valid=True, message="服务可访问")
        return AuthVerifyResult(
            valid=False, message=f"服务响应异常: HTTP {resp.status_code}"
        )

    async def setup_mediaserver(
        self,
        base_url: str,
        api_key: str,
        *,
        name: str,
        type_: str,
        host: str,
        api_key_ms: str,
        play_host: str | None = None,
        webhook_host: str | None = None,
        username: str | None = None,
        password: str | None = None,
        library_path: str | None = None,
        download_dir: str | None = None,
        cache_dir: str | None = None,
        **_: Any,
    ) -> tuple[bool, str | None]:
        """把 Komga / Kavita 装配进 Comic Auto 的媒体服务器配置。

        同时写入漫画缓存/下载目录，使下载目录与媒体库目录保持一致。
        """
        base_url = str(base_url or "").rstrip("/")
        if type_ not in ("komga", "kavita"):
            return False, f"Comic Auto 不支持媒体服务器类型: {type_}"
        if not (username and password):
            return False, "Comic Auto 缺少装配所需的管理员账号密码"

        async with httpx.AsyncClient(
            timeout=self.TIMEOUT, follow_redirects=True
        ) as client:
            try:
                token, error = await self._login(
                    client, base_url, username, password
                )
            except httpx.RequestError as exc:
                return False, f"无法连接到应用: {exc}"
            if token is None:
                return False, f"Comic Auto 登录失败: {error}"
            headers = {"Authorization": f"Bearer {token}"}

            effective_download = download_dir or self.DEFAULT_DOWNLOAD_DIR
            effective_cache = cache_dir or self.DEFAULT_CACHE_DIR
            settings_error = await self._update_settings(
                client,
                base_url,
                headers,
                download_dir=effective_download,
                cache_dir=effective_cache,
            )
            if settings_error:
                return False, settings_error

            payload = {
                "server_url": str(host or "").rstrip("/"),
                "api_key": api_key_ms,
                "is_enabled": True,
                "library_path": library_path or effective_download,
            }
            try:
                resp = await client.put(
                    f"{base_url}/api/v1/app/media-servers/{type_}/",
                    headers=headers,
                    json=payload,
                )
            except httpx.RequestError as exc:
                return False, f"写入媒体服务器失败: {exc}"
            if resp.status_code >= 400:
                return False, f"写入媒体服务器失败: HTTP {resp.status_code}"
            try:
                _, error = self._unwrap(resp.json())
            except json.JSONDecodeError:
                return False, "媒体服务器接口返回异常"
            if error:
                return False, error

            # 回读确认配置已落库
            try:
                verify = await client.get(
                    f"{base_url}/api/v1/app/media-servers/", headers=headers
                )
                data, _ = self._unwrap(verify.json())
                items = data.get("items") if isinstance(data, dict) else None
                if isinstance(items, list) and not any(
                    item.get("server_type") == type_ for item in items
                ):
                    return False, "媒体服务器配置写入后未生效"
            except (httpx.RequestError, json.JSONDecodeError):
                pass

            return True, f"已装配 {name}（{type_}）"

    async def _update_settings(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        headers: dict,
        *,
        download_dir: str,
        cache_dir: str,
    ) -> str | None:
        """合并写入下载/缓存目录，保留其余已有设置。"""
        try:
            resp = await client.get(
                f"{base_url}/api/v1/app/settings/", headers=headers
            )
        except httpx.RequestError as exc:
            return f"读取 Comic Auto 设置失败: {exc}"
        if resp.status_code != 200:
            return f"读取 Comic Auto 设置失败: HTTP {resp.status_code}"
        try:
            data, error = self._unwrap(resp.json())
        except json.JSONDecodeError:
            return "Comic Auto 设置接口返回异常"
        if error:
            return error
        current = data if isinstance(data, dict) else {}

        payload = {
            "cache_dir": cache_dir,
            "download_dir": download_dir,
            "cache_size_limit": current.get("cache_size_limit", 10240),
            "cache_retention_days": current.get("cache_retention_days", 30),
            "proxy_enabled": current.get("proxy_enabled", False),
            "proxy_url": current.get("proxy_url", ""),
        }
        try:
            resp = await client.put(
                f"{base_url}/api/v1/app/settings/",
                headers=headers,
                json=payload,
            )
        except httpx.RequestError as exc:
            return f"写入 Comic Auto 目录设置失败: {exc}"
        if resp.status_code >= 400:
            return f"写入 Comic Auto 目录设置失败: HTTP {resp.status_code}"
        try:
            _, error = self._unwrap(resp.json())
        except json.JSONDecodeError:
            return "目录设置接口返回异常"
        return error

    @staticmethod
    def _unwrap(payload: Any) -> tuple[Any, str | None]:
        """解包 Comic Auto 的统一响应结构。"""
        if isinstance(payload, dict) and "code" in payload:
            if payload.get("code") not in (0, None):
                return None, payload.get("msg") or "接口返回错误"
            return payload.get("data"), None
        return payload, None


register_client(ComicAutoClient.name, ComicAutoClient)
