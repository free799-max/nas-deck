"""二毛读书应用客户端实现。

二毛读书首次启动没有管理员，通过 ``POST /api/auth/setup`` 创建；
已初始化时用邮箱密码登录。统一用户名不是邮箱时映射为
``<用户名>@example.com``，并在结果里回传实际邮箱，供后续自动同步复用。
已存在账号且密码不一致时，用旧密码登录后通过
``PATCH /api/auth/account/password`` 同步为统一密码。
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
from app.services.apps.reader.client import ErmaoClient, ErmaoClientError
from app.services.apps.registry import register_client

DEFAULT_EMAIL_DOMAIN = "example.com"
# 二毛要求密码至少 10 位
MIN_PASSWORD_LENGTH = 10
# 账号/参数错误无需继续轮询
_PERMANENT_ERROR_HINTS = (
    "邮箱或密码不正确",
    "当前密码",
    "账户已停用",
    "UNAUTHORIZED",
    "至少",
    "不能",
    "已存在",
    "已被使用",
)


class ErmaoLibraryClient(AppClient):
    """二毛读书书库服务的账号自动配置客户端。"""

    name = "ermao-library"
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
        """初始化管理员，或登录已有管理员并同步统一密码。"""
        base = str(url or "").strip().rstrip("/")
        if not base:
            return ProvisionResult(ok=False, message="访问地址不能为空")

        email = self._normalize_email(username)
        if len(password) < MIN_PASSWORD_LENGTH:
            return ProvisionResult(
                ok=False,
                message=f"二毛密码至少需要 {MIN_PASSWORD_LENGTH} 位",
                username=email,
            )

        deadline = time.monotonic() + self.PROVISION_TIMEOUT
        last_error = "服务未就绪"

        while time.monotonic() < deadline:
            try:
                async with ErmaoClient(base, timeout=self.TIMEOUT) as client:
                    try:
                        initialized = await client.setup_status()
                    except ErmaoClientError as exc:
                        last_error = str(exc)
                        if self._is_permanent(last_error):
                            return ProvisionResult(
                                ok=False,
                                message=f"读取二毛初始化状态失败: {exc}",
                                username=email,
                            )
                        await asyncio.sleep(5)
                        continue

                    if not initialized:
                        try:
                            await client.setup(email, password)
                        except ErmaoClientError as exc:
                            if self._is_permanent(str(exc)):
                                return ProvisionResult(
                                    ok=False,
                                    message=f"创建二毛管理员失败: {exc}",
                                    username=email,
                                )
                            last_error = str(exc)
                            await asyncio.sleep(5)
                            continue
                        return ProvisionResult(
                            ok=True,
                            message="管理员账号已创建并验证通过",
                            username=email,
                        )

                    try:
                        await client.login(email, password)
                        return ProvisionResult(
                            ok=True,
                            message="账号已配置并验证通过",
                            username=email,
                        )
                    except ErmaoClientError as exc:
                        login_error = str(exc)
                        if not self._is_permanent(login_error):
                            last_error = login_error
                            await asyncio.sleep(5)
                            continue

                    if previous_password and previous_password != password:
                        try:
                            await client.login(email, previous_password)
                        except ErmaoClientError:
                            pass
                        else:
                            try:
                                await client.change_password(
                                    previous_password, password
                                )
                            except ErmaoClientError as exc:
                                return ProvisionResult(
                                    ok=False,
                                    message=f"修改二毛密码失败: {exc}",
                                    username=email,
                                )
                            try:
                                await client.login(email, password)
                            except ErmaoClientError as exc:
                                return ProvisionResult(
                                    ok=False,
                                    message=(
                                        "修改密码后登录验证失败: "
                                        f"{exc}"
                                    ),
                                    username=email,
                                )
                            return ProvisionResult(
                                ok=True,
                                message="账号密码已更新并验证通过",
                                username=email,
                            )

                    return ProvisionResult(
                        ok=False,
                        message=(
                            f"登录二毛失败: {login_error}"
                            "（如已手动初始化，请填写原账号密码）"
                        ),
                        username=email,
                    )
            except httpx.RequestError as exc:
                last_error = f"无法连接到应用: {exc}"
            await asyncio.sleep(5)

        return ProvisionResult(
            ok=False,
            message=f"自动配置超时: {last_error}",
            username=email,
        )

    async def verify_auth(self, config: dict) -> AuthVerifyResult:
        """校验二毛访问地址与账号密码。"""
        base = str(config.get("url") or "").strip().rstrip("/")
        if not base:
            return AuthVerifyResult(valid=False, message="访问地址不能为空")

        auth_type = config.get("auth_type") or "none"
        if auth_type in ("api_key", "apikey"):
            return AuthVerifyResult(
                valid=False,
                message="二毛读书不支持 API Key，请使用账号密码",
            )

        try:
            async with ErmaoClient(base, timeout=self.TIMEOUT) as client:
                if auth_type == "basic":
                    email = self._normalize_email(
                        str(config.get("username") or "")
                    )
                    password = str(config.get("password") or "")
                    if not password:
                        return AuthVerifyResult(
                            valid=False, message="邮箱和密码不能为空"
                        )
                    try:
                        await client.login(email, password)
                    except ErmaoClientError as exc:
                        return AuthVerifyResult(
                            valid=False, message=str(exc)
                        )
                    return AuthVerifyResult(
                        valid=True, message="账号密码验证成功"
                    )

                await client.setup_status()
                return AuthVerifyResult(valid=True, message="服务可访问")
        except httpx.TimeoutException:
            return AuthVerifyResult(
                valid=False, message="连接超时，请检查地址与网络"
            )
        except (httpx.RequestError, ErmaoClientError) as exc:
            return AuthVerifyResult(
                valid=False, message=f"无法连接到应用: {exc}"
            )

    @staticmethod
    def _normalize_email(username: str) -> str:
        """二毛用邮箱登录；普通用户名映射为固定本地邮箱。"""
        raw = str(username or "").strip().lower()
        if "@" in raw:
            return raw
        slug = re.sub(r"[^a-z0-9._-]+", "", raw).strip("._-")
        return f"{slug or 'admin'}@{DEFAULT_EMAIL_DOMAIN}"

    @staticmethod
    def _is_permanent(message: str) -> bool:
        return any(hint in (message or "") for hint in _PERMANENT_ERROR_HINTS)


register_client(ErmaoLibraryClient.name, ErmaoLibraryClient)
