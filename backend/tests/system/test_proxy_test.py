"""代理连通性检测接口与服务测试。"""

import httpx
import pytest

from app.core.exceptions import APIException
from app.services.system.proxy_test_service import (
    normalize_proxy_url,
    proxy_test_service,
)


async def _register_and_login(client, username: str, password: str = "pass123456") -> str:
    resp = await client.post(
        "/api/auth/register", json={"username": username, "password": password}
    )
    assert resp.status_code == 201, resp.text
    login = await client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert login.status_code == 200, login.text
    return login.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class _FakeResponse:
    """只暴露探针需要的 status_code / aclose。"""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    async def aclose(self) -> None:
        return None


class _FakeClient:
    """模拟 httpx.AsyncClient 的 send 路径。"""

    def __init__(self, status_code: int = 200, exc: Exception | None = None) -> None:
        self.status_code = status_code
        self.exc = exc

    def build_request(self, method: str, url: str) -> httpx.Request:
        return httpx.Request(method, url)

    async def send(self, request: httpx.Request, stream: bool = True) -> _FakeResponse:
        if self.exc is not None:
            raise self.exc
        return _FakeResponse(self.status_code)


def test_normalize_proxy_url():
    assert normalize_proxy_url("  http://proxy:8080 ") == "http://proxy:8080"
    assert normalize_proxy_url("") is None
    assert normalize_proxy_url(None) is None
    with pytest.raises(APIException):
        normalize_proxy_url("proxy:8080")


@pytest.mark.asyncio
async def test_probe_success():
    result = await proxy_test_service._probe(
        _FakeClient(204), "http://proxy:8080", "Google", "https://www.google.com"
    )
    assert result["ok"] is True
    assert result["status_code"] == 204
    assert isinstance(result["latency_ms"], int)
    assert result["error"] is None


@pytest.mark.asyncio
async def test_probe_masks_proxy_in_error():
    error = httpx.ConnectError("cannot connect to http://proxy:8080")
    result = await proxy_test_service._probe(
        _FakeClient(exc=error), "http://proxy:8080", "Google", "https://www.google.com"
    )
    assert result["ok"] is False
    assert result["status_code"] is None
    assert "proxy:8080" not in result["error"]
    assert "<代理>" in result["error"]


@pytest.mark.asyncio
async def test_proxy_test_endpoint_uses_saved_config(client, monkeypatch):
    token = await _register_and_login(client, "proxysaved")
    resp = await client.put(
        "/api/settings",
        json={
            "proxy_enabled": True,
            "http_proxy": "http://10.0.0.1:7890",
            "https_proxy": "http://10.0.0.2:7890",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    captured: dict = {}

    async def fake_test(http_proxy=None, https_proxy=None):
        captured["http_proxy"] = http_proxy
        captured["https_proxy"] = https_proxy
        return {
            "proxy": https_proxy,
            "ok_count": 1,
            "total": 2,
            "results": [
                {
                    "name": "Google",
                    "url": "https://www.google.com/generate_204",
                    "ok": True,
                    "status_code": 204,
                    "latency_ms": 120,
                    "error": None,
                },
                {
                    "name": "YouTube",
                    "url": "https://www.youtube.com/generate_204",
                    "ok": False,
                    "status_code": None,
                    "latency_ms": None,
                    "error": "timeout",
                },
            ],
        }

    monkeypatch.setattr(
        "app.api.settings.proxy_test_service.test", fake_test
    )

    resp = await client.post(
        "/api/settings/proxy/test", json={}, headers=_auth(token)
    )
    assert resp.status_code == 200, resp.text
    assert captured == {
        "http_proxy": "http://10.0.0.1:7890",
        "https_proxy": "http://10.0.0.2:7890",
    }
    data = resp.json()["data"]
    assert data["proxy"] == "http://10.0.0.2:7890"
    assert data["ok_count"] == 1
    assert data["total"] == 2
    assert data["results"][1]["ok"] is False


@pytest.mark.asyncio
async def test_proxy_test_endpoint_explicit_empty_means_direct(client, monkeypatch):
    token = await _register_and_login(client, "proxydirect")
    await client.put(
        "/api/settings",
        json={"http_proxy": "http://10.0.0.1:7890"},
        headers=_auth(token),
    )

    captured: dict = {}

    async def fake_test(http_proxy=None, https_proxy=None):
        captured["http_proxy"] = http_proxy
        captured["https_proxy"] = https_proxy
        return {"proxy": None, "ok_count": 0, "total": 1, "results": []}

    monkeypatch.setattr(
        "app.api.settings.proxy_test_service.test", fake_test
    )

    resp = await client.post(
        "/api/settings/proxy/test",
        json={"http_proxy": "", "https_proxy": ""},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    assert captured == {"http_proxy": "", "https_proxy": ""}
    assert resp.json()["data"]["proxy"] is None


@pytest.mark.asyncio
async def test_proxy_test_endpoint_ignores_disabled_saved_proxy(client, monkeypatch):
    token = await _register_and_login(client, "proxyoff")
    await client.put(
        "/api/settings",
        json={
            "proxy_enabled": False,
            "http_proxy": "http://10.0.0.1:7890",
            "https_proxy": "http://10.0.0.1:7890",
        },
        headers=_auth(token),
    )

    captured: dict = {}

    async def fake_test(http_proxy=None, https_proxy=None):
        captured["http_proxy"] = http_proxy
        captured["https_proxy"] = https_proxy
        return {"proxy": None, "ok_count": 0, "total": 1, "results": []}

    monkeypatch.setattr(
        "app.api.settings.proxy_test_service.test", fake_test
    )

    resp = await client.post(
        "/api/settings/proxy/test", json={}, headers=_auth(token)
    )
    assert resp.status_code == 200, resp.text
    assert captured == {"http_proxy": "", "https_proxy": ""}


@pytest.mark.asyncio
async def test_proxy_enabled_defaults_false_and_updates(client):
    token = await _register_and_login(client, "proxyenable")

    resp = await client.get("/api/settings", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["proxy_enabled"] is False

    resp = await client.put(
        "/api/settings",
        json={"proxy_enabled": True, "https_proxy": "http://127.0.0.1:7890"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["proxy_enabled"] is True
    assert data["https_proxy"] == "http://127.0.0.1:7890"

    # 未提交 proxy_enabled 的局部更新不应改动开关
    resp = await client.put(
        "/api/settings",
        json={"service_port_start": 12000},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["proxy_enabled"] is True


@pytest.mark.asyncio
async def test_proxy_test_endpoint_rejects_invalid_proxy(client):
    token = await _register_and_login(client, "proxybad")
    resp = await client.post(
        "/api/settings/proxy/test",
        json={"https_proxy": "127.0.0.1:7890"},
        headers=_auth(token),
    )
    assert resp.status_code == 400, resp.text
    assert "http://" in resp.json()["message"]
