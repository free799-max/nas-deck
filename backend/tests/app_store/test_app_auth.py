"""应用客户端认证检测测试。"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.exceptions import APIException
from app.services.apps import get_client
from app.services.apps.moviepilot import MoviePilotClient
from app.services.apps.qbittorrent import QBittorrentClient


def _resp(
    status_code: int,
    json_data=None,
    text: str | None = None,
    method: str = "GET",
    url: str = "http://test",
) -> httpx.Response:
    """构造带 request 信息的 httpx Response，便于 raise_for_status。"""
    if text is not None:
        return httpx.Response(status_code, text=text, request=httpx.Request(method, url))
    return httpx.Response(status_code, json=json_data, request=httpx.Request(method, url))


@pytest.mark.asyncio
async def test_moviepilot_client_api_key_success():
    """API Key 认证成功时返回 valid=True，并携带正确请求头。"""
    with patch("app.services.apps.moviepilot.client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.get = AsyncMock(
            return_value=_resp(200, json_data=[{"name": "admin"}])
        )

        result = await MoviePilotClient().verify_auth(
            {
                "url": "http://192.168.1.192:3003",
                "auth_type": "api_key",
                "api_key": "test-key",
            }
        )

        assert result.valid is True
        assert "认证成功" in (result.message or "")
        instance.get.assert_awaited_once()
        _, kwargs = instance.get.call_args
        assert kwargs["headers"]["X-API-KEY"] == "test-key"


@pytest.mark.asyncio
async def test_moviepilot_client_api_key_unauthorized():
    """API Key 错误时返回 valid=False。"""
    with patch("app.services.apps.moviepilot.client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.get = AsyncMock(return_value=_resp(401))

        result = await MoviePilotClient().verify_auth(
            {
                "url": "http://192.168.1.192:3003",
                "auth_type": "api_key",
                "api_key": "wrong-key",
            }
        )

        assert result.valid is False
        assert "API Key 认证失败" in (result.message or "")


@pytest.mark.asyncio
async def test_moviepilot_client_basic_success():
    """用户名/密码认证成功时，先登录再请求受保护接口。"""
    with patch("app.services.apps.moviepilot.client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.post = AsyncMock(
            return_value=_resp(
                200,
                json_data={
                    "access_token": "test-token",
                    "token_type": "bearer",
                    "user_name": "admin",
                },
                method="POST",
            )
        )
        instance.get = AsyncMock(
            return_value=_resp(200, json_data=[{"name": "admin"}])
        )

        result = await MoviePilotClient().verify_auth(
            {
                "url": "http://192.168.1.192:3003",
                "auth_type": "basic",
                "username": "admin",
                "password": "admin123",
            }
        )

        assert result.valid is True
        assert "用户名/密码认证成功" in (result.message or "")
        instance.post.assert_awaited_once()
        _, post_kwargs = instance.post.call_args
        assert post_kwargs["data"]["username"] == "admin"
        assert post_kwargs["data"]["password"] == "admin123"

        instance.get.assert_awaited_once()
        _, get_kwargs = instance.get.call_args
        assert get_kwargs["headers"]["Authorization"] == "Bearer test-token"


@pytest.mark.asyncio
async def test_moviepilot_client_basic_login_failure():
    """用户名/密码错误时返回 valid=False。"""
    with patch("app.services.apps.moviepilot.client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.post = AsyncMock(return_value=_resp(401, method="POST"))

        result = await MoviePilotClient().verify_auth(
            {
                "url": "http://192.168.1.192:3003",
                "auth_type": "basic",
                "username": "admin",
                "password": "wrong",
            }
        )

        assert result.valid is False
        assert "用户名或密码错误" in (result.message or "")


@pytest.mark.asyncio
async def test_moviepilot_client_basic_missing_token():
    """登录接口未返回 token 时返回 valid=False。"""
    with patch("app.services.apps.moviepilot.client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.post = AsyncMock(return_value=_resp(200, json_data={}, method="POST"))

        result = await MoviePilotClient().verify_auth(
            {
                "url": "http://192.168.1.192:3003",
                "auth_type": "basic",
                "username": "admin",
                "password": "admin123",
            }
        )

        assert result.valid is False
        assert "未返回 Token" in (result.message or "")


@pytest.mark.asyncio
async def test_moviepilot_client_network_error():
    """网络异常时返回 valid=False。"""
    with patch("app.services.apps.moviepilot.client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.get = AsyncMock(side_effect=httpx.ConnectError("connection failed"))

        result = await MoviePilotClient().verify_auth(
            {
                "url": "http://192.168.1.192:3003",
                "auth_type": "api_key",
                "api_key": "test-key",
            }
        )

        assert result.valid is False
        assert "无法连接到应用" in (result.message or "")


@pytest.mark.asyncio
async def test_moviepilot_client_empty_url():
    """访问地址为空时返回 valid=False。"""
    result = await MoviePilotClient().verify_auth({"url": "", "auth_type": "none"})

    assert result.valid is False
    assert "访问地址不能为空" in (result.message or "")


def test_registry_returns_moviepilot_client():
    """注册表能正确返回 MoviePilotClient。"""
    client_cls = get_client("moviepilot")
    assert client_cls is MoviePilotClient


def test_registry_unknown_app_raises():
    """未注册的应用返回 APIException。"""
    with pytest.raises(APIException) as exc_info:
        get_client("not-exist")
    assert "暂无客户端支持" in str(exc_info.value)


@pytest.mark.asyncio
async def test_qbittorrent_client_basic_success():
    """用户名/密码认证成功时返回 valid=True。"""
    with patch("app.services.apps.qbittorrent.client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.post = AsyncMock(
            return_value=_resp(
                200,
                text="Ok.",
                method="POST",
                url="http://test/api/v2/auth/login",
            )
        )
        instance.get = AsyncMock(
            return_value=_resp(
                200,
                text="v5.2.0",
                url="http://test/api/v2/app/version",
            )
        )

        result = await QBittorrentClient().verify_auth(
            {
                "url": "http://192.168.1.192:8080",
                "auth_type": "basic",
                "username": "admin",
                "password": "admin123",
            }
        )

        assert result.valid is True
        assert "用户名/密码认证成功" in (result.message or "")
        instance.post.assert_awaited_once()
        _, post_kwargs = instance.post.call_args
        assert post_kwargs["data"]["username"] == "admin"
        assert post_kwargs["data"]["password"] == "admin123"
        instance.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_qbittorrent_client_basic_success_204():
    """qBittorrent 登录返回 204 No Content 时也视为成功。"""
    with patch("app.services.apps.qbittorrent.client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.post = AsyncMock(
            return_value=_resp(
                204,
                method="POST",
                url="http://test/api/v2/auth/login",
            )
        )
        instance.get = AsyncMock(
            return_value=_resp(
                200,
                text="v5.2.0",
                url="http://test/api/v2/app/version",
            )
        )

        result = await QBittorrentClient().verify_auth(
            {
                "url": "http://192.168.1.192:8080",
                "auth_type": "basic",
                "username": "admin",
                "password": "admin123",
            }
        )

        assert result.valid is True
        assert "用户名/密码认证成功" in (result.message or "")


@pytest.mark.asyncio
async def test_qbittorrent_client_basic_unauthorized():
    """用户名/密码错误时返回 valid=False。"""
    with patch("app.services.apps.qbittorrent.client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.post = AsyncMock(
            return_value=_resp(
                200,
                text="Fails.",
                method="POST",
                url="http://test/api/v2/auth/login",
            )
        )

        result = await QBittorrentClient().verify_auth(
            {
                "url": "http://192.168.1.192:8080",
                "auth_type": "basic",
                "username": "admin",
                "password": "wrong",
            }
        )

        assert result.valid is False
        assert "用户名或密码错误" in (result.message or "")


@pytest.mark.asyncio
async def test_qbittorrent_client_basic_forbidden():
    """qBittorrent 返回 403（如 CSRF 保护触发）时给出明确提示。"""
    with patch("app.services.apps.qbittorrent.client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.post = AsyncMock(
            return_value=_resp(
                403,
                method="POST",
                url="http://test/api/v2/auth/login",
            )
        )

        result = await QBittorrentClient().verify_auth(
            {
                "url": "http://192.168.1.192:8080",
                "auth_type": "basic",
                "username": "admin",
                "password": "admin123",
            }
        )

        assert result.valid is False
        assert "认证被拒绝" in (result.message or "")
        _, post_kwargs = instance.post.call_args
        assert post_kwargs["headers"]["Referer"] == "http://192.168.1.192:8080"


@pytest.mark.asyncio
async def test_qbittorrent_client_api_key_success():
    """API Key 认证成功时返回 valid=True，并携带正确请求头。"""
    with patch("app.services.apps.qbittorrent.client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.get = AsyncMock(
            return_value=_resp(
                200,
                text="v5.2.0",
                url="http://test/api/v2/app/version",
            )
        )

        result = await QBittorrentClient().verify_auth(
            {
                "url": "http://192.168.1.192:8080",
                "auth_type": "api_key",
                "api_key": "qbt_zdWwWjfqjCyGwfD3B9Jh5qRRqDTw",
            }
        )

        assert result.valid is True
        assert "API Key 认证成功" in (result.message or "")
        instance.get.assert_awaited_once()
        _, get_kwargs = instance.get.call_args
        assert get_kwargs["headers"]["Authorization"] == "Bearer qbt_zdWwWjfqjCyGwfD3B9Jh5qRRqDTw"


@pytest.mark.asyncio
async def test_qbittorrent_client_api_key_unauthorized():
    """API Key 错误时返回 valid=False。"""
    with patch("app.services.apps.qbittorrent.client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.get = AsyncMock(return_value=_resp(403, url="http://test/api/v2/app/version"))

        result = await QBittorrentClient().verify_auth(
            {
                "url": "http://192.168.1.192:8080",
                "auth_type": "api_key",
                "api_key": "qbt_wrong",
            }
        )

        assert result.valid is False
        assert "API Key 认证失败" in (result.message or "")


@pytest.mark.asyncio
async def test_qbittorrent_client_network_error():
    """网络异常时返回 valid=False。"""
    with patch("app.services.apps.qbittorrent.client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.get = AsyncMock(side_effect=httpx.ConnectError("connection failed"))

        result = await QBittorrentClient().verify_auth(
            {
                "url": "http://192.168.1.192:8080",
                "auth_type": "api_key",
                "api_key": "qbt_test",
            }
        )

        assert result.valid is False
        assert "无法连接到应用" in (result.message or "")


@pytest.mark.asyncio
async def test_qbittorrent_client_empty_url():
    """访问地址为空时返回 valid=False。"""
    result = await QBittorrentClient().verify_auth(
        {"url": "", "auth_type": "api_key", "api_key": "qbt_test"}
    )

    assert result.valid is False
    assert "访问地址不能为空" in (result.message or "")


def test_registry_returns_qbittorrent_client():
    """注册表能正确返回 QBittorrentClient。"""
    client_cls = get_client("qbittorrent")
    assert client_cls is QBittorrentClient
