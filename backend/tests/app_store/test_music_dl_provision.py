"""music-dl 部署后账号与下载目录自动配置测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.apps import ProvisionResult
from app.services.apps.music_dl import MusicDLClient
from app.services.orchestration import orchestration_service
from app.services.orchestration import provisioning as provisioning_module


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


def _resp(
    status_code: int,
    json_data=None,
    text: str | None = None,
    headers: dict | None = None,
    method: str = "GET",
    url: str = "http://test",
) -> httpx.Response:
    if text is not None:
        return httpx.Response(
            status_code,
            text=text,
            headers=headers,
            request=httpx.Request(method, url),
        )
    return httpx.Response(
        status_code,
        json=json_data,
        headers=headers,
        request=httpx.Request(method, url),
    )


def _mock_http():
    patcher = patch("httpx.AsyncClient")
    MockClient = patcher.start()
    instance = MockClient.return_value
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    instance.get = AsyncMock()
    instance.post = AsyncMock()
    return patcher, instance


def _settings(download_dir: str = "data/downloads") -> dict:
    return {
        "embedDownload": True,
        "downloadDir": download_dir,
        "downloadFilenameTemplate": "{artist} - {name}",
    }


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_music_dl_provision_first_run_sets_account_and_download_dir():
    """首次启动解析初始化令牌创建管理员，并写入共享下载目录。"""
    patcher, instance = _mock_http()
    try:
        instance.get = AsyncMock(
            side_effect=[
                _resp(200, json_data=_settings()),  # 服务就绪探测
                _resp(
                    401,
                    json_data={
                        "error": "请先初始化管理员账号",
                        "setupRequired": True,
                    },
                ),  # 未初始化
                _resp(200, json_data={}),  # setup 后会话校验
                _resp(200, json_data=_settings()),  # 读取当前设置
            ]
        )
        instance.post = AsyncMock(
            side_effect=[
                _resp(200, text="<html>ok</html>", method="POST"),  # /setup
                _resp(
                    200,
                    json_data=_settings("/app/media/downloads"),
                    method="POST",
                ),  # /settings
            ]
        )

        async def logs_reader() -> str:
            return (
                "2026/10/24 08:05:20 SLOW SQL\n"
                "Web setup token: AbCdEf_123-token\n"
                "Open /music/setup and keep this startup terminal private\n"
            )

        result = await MusicDLClient().provision(
            url="http://192.168.1.17:10000",
            username="nasadmin",
            password="Unified#Pass1",
            logs_reader=logs_reader,
            download_dir="/app/media/downloads",
        )

        assert result.ok is True
        assert result.username == "nasadmin"
        assert result.download_dir == "/app/media/downloads"
        assert "下载目录 /app/media/downloads" in (result.message or "")

        setup_call = instance.post.call_args_list[0]
        assert setup_call.args[0].endswith("/music/setup")
        assert setup_call.kwargs["data"]["setup_token"] == "AbCdEf_123-token"
        assert setup_call.kwargs["data"]["username"] == "nasadmin"
        assert setup_call.kwargs["data"]["password_confirm"] == "Unified#Pass1"

        settings_call = instance.post.call_args_list[1]
        assert settings_call.args[0].endswith("/music/settings")
        assert settings_call.kwargs["json"]["downloadDir"] == "/app/media/downloads"
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_music_dl_provision_logs_in_existing_admin_and_reuses_dir():
    """已初始化时直接登录；目录已正确时不重复保存。"""
    patcher, instance = _mock_http()
    try:
        instance.get = AsyncMock(
            side_effect=[
                _resp(200, json_data=_settings()),  # 服务就绪
                _resp(401, json_data={"error": "请先登录"}),  # 未登录
                _resp(200, json_data={}),  # 登录后会话校验
                _resp(
                    200, json_data=_settings("/app/media/downloads")
                ),  # 目录已是目标值
            ]
        )
        instance.post = AsyncMock(
            return_value=_resp(
                302,
                text="",
                headers={"location": "/music/"},
                method="POST",
            )
        )

        result = await MusicDLClient().provision(
            url="http://192.168.1.17:10000/music/",
            username="nasadmin",
            password="Unified#Pass1",
            download_dir="/app/media/downloads",
        )

        assert result.ok is True
        assert instance.post.await_count == 1
        login_call = instance.post.call_args_list[0]
        assert login_call.args[0] == "http://192.168.1.17:10000/music/login"
        assert login_call.kwargs["data"]["username"] == "nasadmin"
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_music_dl_provision_reports_password_mismatch_without_loop():
    """统一密码与已有管理员不一致时明确失败，不反复触发登录锁定。"""
    patcher, instance = _mock_http()
    try:
        instance.get = AsyncMock(
            side_effect=[
                _resp(200, json_data=_settings()),
                _resp(401, json_data={"error": "请先登录"}),
                _resp(200, json_data={}),  # 旧密码登录后的会话校验
            ]
        )
        instance.post = AsyncMock(
            return_value=_resp(
                302,
                text="",
                headers={"location": "/music/"},
                method="POST",
            )
        )

        result = await MusicDLClient().provision(
            url="http://192.168.1.17:10000",
            username="nasadmin",
            password="Unified#Pass1",
            previous_password="Stored#Pass1",
        )

        assert result.ok is False
        assert "密码与统一密码不一致" in (result.message or "")
        # 旧密码已验证成功，不再用目标密码触发登录失败
        assert instance.post.await_count == 1
        assert (
            instance.post.call_args.kwargs["data"]["password"] == "Stored#Pass1"
        )
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_music_dl_provision_falls_back_to_target_when_previous_stale():
    """旧密码失效时等待锁定结束，再用统一密码登录成功。"""
    patcher, instance = _mock_http()
    try:
        instance.get = AsyncMock(
            side_effect=[
                _resp(200, json_data=_settings()),
                _resp(401, json_data={"error": "请先登录"}),
                _resp(200, json_data={}),  # 目标密码登录后的会话校验
            ]
        )
        instance.post = AsyncMock(
            side_effect=[
                _resp(
                    200,
                    text=(
                        '<div class="error-msg auth-error">'
                        "<i></i> 用户名或密码不正确</div>"
                    ),
                    method="POST",
                ),
                _resp(
                    302,
                    text="",
                    headers={"location": "/music/"},
                    method="POST",
                ),
            ]
        )

        with patch(
            "app.services.apps.music_dl.client.asyncio.sleep",
            new=AsyncMock(),
        ):
            result = await MusicDLClient().provision(
                url="http://192.168.1.17:10000",
                username="nasadmin",
                password="Unified#Pass1",
                previous_password="Stale#Pass1",
            )

        assert result.ok is True
        assert instance.post.await_count == 2
        assert (
            instance.post.call_args_list[-1].kwargs["data"]["password"]
            == "Unified#Pass1"
        )
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_music_dl_provision_timeout():
    """服务一直不可达时超时失败。"""
    patcher, instance = _mock_http()
    try:
        instance.get = AsyncMock(
            side_effect=httpx.ConnectError("connection refused")
        )
        client = MusicDLClient()
        client.PROVISION_TIMEOUT = 0.5

        with patch(
            "app.services.apps.music_dl.client.asyncio.sleep",
            new=AsyncMock(),
        ):
            result = await client.provision(
                url="http://192.168.1.17:10000",
                username="nasadmin",
                password="Unified#Pass1",
            )

        assert result.ok is False
        assert "自动配置超时" in (result.message or "")
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_music_dl_verify_auth_basic():
    """认证检测用账号密码登录并校验会话。"""
    patcher, instance = _mock_http()
    try:
        instance.post = AsyncMock(
            return_value=_resp(
                302,
                text="",
                headers={"location": "/music/"},
                method="POST",
            )
        )
        instance.get = AsyncMock(return_value=_resp(200, json_data={}))

        result = await MusicDLClient().verify_auth(
            {
                "url": "http://192.168.1.17:10000",
                "auth_type": "basic",
                "username": "nasadmin",
                "password": "Unified#Pass1",
            }
        )

        assert result.valid is True
        args, kwargs = instance.post.call_args
        assert args[0].endswith("/music/login")
        assert kwargs["data"]["username"] == "nasadmin"
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_resolve_music_download_dir_prefers_shared_downloads(monkeypatch):
    """共享卷同时挂载 downloads/library 时优先使用 downloads。"""
    monkeypatch.setattr(
        provisioning_module, "async_session", lambda: _FakeSession()
    )
    monkeypatch.setattr(
        orchestration_service,
        "get_group",
        AsyncMock(
            return_value=SimpleNamespace(
                shared_config={
                    "volumes": [
                        {"container_path": "/mnt/music"},
                        {"container_path": "/app/media/music"},
                        {"container_path": "/app/media/downloads"},
                    ]
                }
            )
        ),
    )

    path = await orchestration_service._resolve_music_download_dir(1)

    assert path == "/app/media/downloads"


@pytest.mark.asyncio
async def test_resolve_music_download_dir_falls_back_to_shared_root(monkeypatch):
    """仅挂载共享根目录时使用其 downloads 子目录。"""
    monkeypatch.setattr(
        provisioning_module, "async_session", lambda: _FakeSession()
    )
    monkeypatch.setattr(
        orchestration_service,
        "get_group",
        AsyncMock(
            return_value=SimpleNamespace(
                shared_config={
                    "volumes": [{"container_path": "/mnt/music"}],
                }
            )
        ),
    )

    path = await orchestration_service._resolve_music_download_dir(1)

    assert path == "/mnt/music/downloads"


@pytest.mark.asyncio
async def test_provision_app_passes_shared_download_dir_to_music_dl(monkeypatch):
    """调度层只给 music-dl 传入共享下载目录，并落库配置结果。"""
    seen: dict = {}

    class _FakeClient:
        async def provision(self, **kwargs):
            seen.update(kwargs)
            return ProvisionResult(
                ok=True,
                message="ok",
                username=kwargs["username"],
                download_dir=kwargs.get("download_dir"),
            )

    write = AsyncMock()
    monkeypatch.setattr(
        orchestration_service,
        "_resolve_provision_client",
        lambda app_name: _FakeClient(),
    )
    monkeypatch.setattr(
        orchestration_service, "_make_logs_reader", lambda project: None
    )
    monkeypatch.setattr(
        orchestration_service,
        "_resolve_music_download_dir",
        AsyncMock(return_value="/app/media/downloads"),
    )
    monkeypatch.setattr(orchestration_service, "_write_provision_result", write)

    result = await orchestration_service._provision_app(
        1,
        "music-dl",
        {"username": "nasadmin", "password": "Unified#Pass1"},
        "http://host:10000",
        "music-auto-music-dl",
    )

    assert result.ok is True
    assert seen["download_dir"] == "/app/media/downloads"
    assert write.await_args.args[3].download_dir == "/app/media/downloads"
