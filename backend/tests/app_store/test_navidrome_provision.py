"""Navidrome 部署后管理员自动配置测试。"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.apps.navidrome import NavidromeClient


def _resp(
    status_code: int,
    json_data=None,
    method: str = "GET",
    url: str = "http://test",
) -> httpx.Response:
    return httpx.Response(
        status_code, json=json_data, request=httpx.Request(method, url)
    )


def _login_payload(username: str = "admin") -> dict:
    return {
        "id": "uid1",
        "token": "nd-token",
        "username": username,
        "isAdmin": True,
    }


def _mock_http():
    patcher = patch("httpx.AsyncClient")
    MockClient = patcher.start()
    instance = MockClient.return_value
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    instance.get = AsyncMock()
    instance.post = AsyncMock()
    instance.put = AsyncMock()
    return patcher, instance


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_navidrome_provision_creates_first_admin():
    """首次启动通过 createAdmin 创建管理员。"""
    patcher, instance = _mock_http()
    try:
        instance.get = AsyncMock(return_value=_resp(200, json_data="."))
        instance.post = AsyncMock(
            side_effect=[
                _resp(401, json_data={"error": "Invalid username or password"}),
                _resp(200, json_data=_login_payload(username="nasadmin")),
            ]
        )

        result = await NavidromeClient().provision(
            url="http://192.168.1.17:10002",
            username="nasadmin",
            password="Unified#Pass1",
        )

        assert result.ok is True
        assert result.username == "nasadmin"
        create_call = instance.post.call_args_list[1]
        assert create_call.args[0].endswith("/auth/createAdmin")
        assert create_call.kwargs["json"] == {
            "username": "nasadmin",
            "password": "Unified#Pass1",
        }
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_navidrome_provision_already_configured():
    """目标密码已生效时直接成功。"""
    patcher, instance = _mock_http()
    try:
        instance.get = AsyncMock(return_value=_resp(200, json_data="."))
        instance.post = AsyncMock(
            return_value=_resp(200, json_data=_login_payload())
        )

        result = await NavidromeClient().provision(
            url="http://192.168.1.17:10002",
            username="admin",
            password="Unified#Pass1",
        )

        assert result.ok is True
        assert instance.post.await_count == 1
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_navidrome_provision_changes_password_with_previous():
    """统一密码变化时用旧密码登录并通过 PUT 改密。"""
    patcher, instance = _mock_http()
    try:
        instance.get = AsyncMock(
            side_effect=[
                _resp(200, json_data="."),  # /ping
                _resp(
                    200,
                    json_data={
                        "id": "uid1",
                        "userName": "admin",
                        "name": "Admin",
                        "email": "",
                        "isAdmin": True,
                        "scrobbleFilter": "",
                    },
                ),  # /api/user/uid1
            ]
        )
        instance.post = AsyncMock(
            side_effect=[
                _resp(401, json_data={"error": "Invalid username or password"}),
                _resp(200, json_data=_login_payload()),  # 旧密码登录
                _resp(200, json_data=_login_payload()),  # 新密码复验
            ]
        )
        instance.put = AsyncMock(
            return_value=_resp(200, json_data=_login_payload())
        )

        result = await NavidromeClient().provision(
            url="http://192.168.1.17:10002",
            username="admin",
            password="Unified#Pass1",
            previous_password="Stored#Pass1",
        )

        assert result.ok is True
        _, kwargs = instance.put.call_args
        assert kwargs["json"]["password"] == "Unified#Pass1"
        assert kwargs["json"]["currentPassword"] == "Stored#Pass1"
        assert kwargs["headers"]["x-nd-authorization"] == "Bearer nd-token"
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_navidrome_provision_existing_admin_unknown_password():
    """已有管理员且密码未知时给出明确失败提示。"""
    patcher, instance = _mock_http()
    try:
        instance.get = AsyncMock(return_value=_resp(200, json_data="."))
        instance.post = AsyncMock(
            side_effect=[
                _resp(401, json_data={"error": "Invalid username or password"}),
                _resp(400, json_data={"error": "admin already exists"}),
            ]
        )

        result = await NavidromeClient().provision(
            url="http://192.168.1.17:10002",
            username="admin",
            password="Unified#Pass1",
        )

        assert result.ok is False
        assert "密码与统一密码不一致" in (result.message or "")
    finally:
        patcher.stop()
