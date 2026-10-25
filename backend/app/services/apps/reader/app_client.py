"""Reader 应用客户端实现。

Reader（hectorqin/reader）默认不启用登录；编排部署时通过
``READER_APP_SECURE=true`` 打开登录认证。首次配置调用
``POST /reader3/login`` 并传 ``isLogin=false`` 注册管理员，已有账号时
直接登录。Reader 每次登录都会轮换 ``accessToken``，因此不长期保存
令牌，自动同步等场景用账号密码重新登录即可。
"""

from __future__ import annotations

import asyncio
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

# Reader 用户名要求 5 位以上且只能包含字母和数字
_USERNAME_ALLOWED = re.compile(r"[^A-Za-z0-9]+")
# 参数本身不合法时无需重试（继续轮询只会得到同样的错误）
_INPUT_ERROR_HINTS = (
    "不能低于",
    "只能由",
    "不能为非法",
    "请输入",
)


class ReaderAppClient(AppClient):
    """Reader 小说阅读服务器的账号自动配置客户端。"""

    name = "reader"
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
        """注册或登录 Reader 管理员，并同步统一账号密码。"""
        base = str(url or "").strip().rstrip("/")
        if not base:
            return ProvisionResult(ok=False, message="访问地址不能为空")

        target = self._normalize_username(username)
        deadline = time.monotonic() + self.PROVISION_TIMEOUT
        last_error = "服务未就绪"

        while time.monotonic() < deadline:
            try:
                async with httpx.AsyncClient(
                    timeout=self.TIMEOUT,
                    follow_redirects=True,
                ) as client:
                    registered = await self._login(
                        client, base, target, password, is_login=False
                    )
                    if registered.get("isSuccess"):
                        return self._success(
                            registered, target, "管理员账号已创建并验证通过"
                        )

                    register_error = self._error(registered, "注册失败")

                    logged_in = await self._login(
                        client, base, target, password, is_login=True
                    )
                    if logged_in.get("isSuccess"):
                        return self._success(
                            logged_in, target, "账号已配置并验证通过"
                        )

                    if previous_password and previous_password != password:
                        old = await self._login(
                            client,
                            base,
                            target,
                            previous_password,
                            is_login=True,
                        )
                        if old.get("isSuccess"):
                            reset = await self._reset_password(
                                client, base, target, password, api_key
                            )
                            if not reset.get("isSuccess"):
                                reset_error = self._error(reset, "未知错误")
                                if "不支持的操作" in reset_error:
                                    reset_error = (
                                        "Reader 未配置管理密码"
                                        "（READER_APP_SECUREKEY），无法自动改密；"
                                        "请手动重置密码或重新部署数据卷"
                                    )
                                return ProvisionResult(
                                    ok=False,
                                    message=(
                                        "旧密码验证成功，但修改密码失败: "
                                        f"{reset_error}"
                                    ),
                                )
                            verified = await self._login(
                                client, base, target, password, is_login=True
                            )
                            if verified.get("isSuccess"):
                                return self._success(
                                    verified,
                                    target,
                                    "账号密码已更新并验证通过",
                                )
                            return ProvisionResult(
                                ok=False,
                                message="修改密码后登录验证失败",
                            )

                    last_error = register_error
                    if "用户名已被占用" in register_error:
                        return ProvisionResult(
                            ok=False,
                            message=(
                                "账号已存在且密码与统一密码不一致，"
                                "请手动重置密码或重新部署数据卷"
                            ),
                            username=target,
                        )
                    if any(
                        hint in register_error
                        for hint in _INPUT_ERROR_HINTS
                    ):
                        return ProvisionResult(
                            ok=False,
                            message=register_error,
                            username=target,
                        )
            except httpx.RequestError as exc:
                last_error = f"无法连接到应用: {exc}"
            await asyncio.sleep(5)

        return ProvisionResult(
            ok=False,
            message=f"自动配置超时: {last_error}",
            username=target,
        )

    async def verify_auth(self, config: dict) -> AuthVerifyResult:
        """校验 Reader 访问地址与认证配置。"""
        base = str(config.get("url") or "").strip().rstrip("/")
        if not base:
            return AuthVerifyResult(valid=False, message="访问地址不能为空")

        auth_type = config.get("auth_type") or "none"
        try:
            async with httpx.AsyncClient(
                timeout=self.TIMEOUT,
                follow_redirects=True,
            ) as client:
                if auth_type == "basic":
                    username = self._normalize_username(
                        str(config.get("username") or "")
                    )
                    password = str(config.get("password") or "")
                    if not password:
                        return AuthVerifyResult(
                            valid=False, message="用户名和密码不能为空"
                        )
                    payload = await self._login(
                        client, base, username, password, is_login=True
                    )
                    if payload.get("isSuccess"):
                        return AuthVerifyResult(
                            valid=True, message="账号密码验证成功"
                        )
                    return AuthVerifyResult(
                        valid=False,
                        message=self._error(payload, "账号密码验证失败"),
                    )

                if auth_type in ("api_key", "apikey"):
                    token = str(config.get("api_key") or "").strip()
                    if not token:
                        return AuthVerifyResult(
                            valid=False, message="访问 Token 不能为空"
                        )
                    resp = await client.get(
                        f"{base}/reader3/getShelfBookWithCacheInfo",
                        params={"accessToken": token},
                    )
                    if resp.status_code != 200:
                        return AuthVerifyResult(
                            valid=False,
                            message=f"服务响应异常: HTTP {resp.status_code}",
                        )
                    try:
                        payload = resp.json()
                    except ValueError:
                        payload = {}
                    if isinstance(payload, dict) and payload.get("isSuccess"):
                        return AuthVerifyResult(
                            valid=True, message="访问 Token 验证成功"
                        )
                    message = (
                        payload.get("errorMsg")
                        if isinstance(payload, dict)
                        else None
                    )
                    return AuthVerifyResult(
                        valid=False,
                        message=str(message or "访问 Token 验证失败"),
                    )

                resp = await client.get(f"{base}/reader3/getUserInfo")
                if resp.status_code != 200:
                    return AuthVerifyResult(
                        valid=False,
                        message=f"服务响应异常: HTTP {resp.status_code}",
                    )
                try:
                    payload = resp.json()
                except ValueError:
                    payload = {}
                data = (
                    payload.get("data")
                    if isinstance(payload, dict)
                    else None
                )
                if isinstance(data, dict) and data.get("secure"):
                    return AuthVerifyResult(
                        valid=False,
                        message=(
                            "Reader 已开启登录认证，请使用账号密码"
                        ),
                    )
                return AuthVerifyResult(valid=True, message="服务可访问")
        except httpx.TimeoutException:
            return AuthVerifyResult(
                valid=False, message="连接超时，请检查地址与网络"
            )
        except httpx.RequestError as exc:
            return AuthVerifyResult(
                valid=False, message=f"无法连接到应用: {exc}"
            )

    @staticmethod
    def _normalize_username(username: str) -> str:
        """把统一用户名转换为 Reader 允许的形式（字母数字、至少 5 位）。"""
        raw = str(username or "").strip()
        if re.fullmatch(r"[A-Za-z0-9]{5,}", raw):
            return raw
        cleaned = _USERNAME_ALLOWED.sub("", raw)
        return cleaned if len(cleaned) >= 5 else "admin"

    @staticmethod
    async def _login(
        client: httpx.AsyncClient,
        base: str,
        username: str,
        password: str,
        *,
        is_login: bool,
    ) -> dict:
        """调用登录接口；``isLogin=false`` 表示首次注册。"""
        resp = await client.post(
            f"{base}/reader3/login",
            json={
                "username": username,
                "password": password,
                "isLogin": is_login,
            },
        )
        if resp.status_code >= 400:
            return {
                "isSuccess": False,
                "errorMsg": f"HTTP {resp.status_code}",
            }
        try:
            payload = resp.json()
        except ValueError:
            return {
                "isSuccess": False,
                "errorMsg": "登录接口返回的不是 JSON",
            }
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    async def _reset_password(
        client: httpx.AsyncClient,
        base: str,
        username: str,
        password: str,
        secure_key: str | None,
    ) -> dict:
        """用管理密钥重置密码（需已通过旧密码登录取得会话）。"""
        params = {"secureKey": secure_key} if secure_key else None
        resp = await client.post(
            f"{base}/reader3/resetPassword",
            params=params,
            json={"username": username, "password": password},
        )
        if resp.status_code >= 400:
            return {
                "isSuccess": False,
                "errorMsg": f"HTTP {resp.status_code}",
            }
        try:
            payload = resp.json()
        except ValueError:
            return {
                "isSuccess": False,
                "errorMsg": "重置密码接口返回的不是 JSON",
            }
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _error(payload: dict, fallback: str) -> str:
        message = payload.get("errorMsg")
        return str(message) if message else fallback

    def _success(
        self, _payload: dict, username: str, message: str
    ) -> ProvisionResult:
        # Reader 每次登录都会轮换 accessToken，令牌不适合长期保存；
        # 自动同步等场景用账号密码重新登录即可
        return ProvisionResult(
            ok=True,
            message=message,
            username=username,
        )


register_client(ReaderAppClient.name, ReaderAppClient)
