"""服务端口建议接口（GET /api/settings/port-suggestions）测试。"""

import pytest


async def _register_and_login(client, username: str, password: str = "pass123456") -> str:
    """注册用户并登录，返回 access_token。"""
    resp = await client.post("/api/auth/register", json={
        "username": username, "password": password,
    })
    assert resp.status_code == 201, resp.text
    login_resp = await client.post("/api/auth/login", json={
        "username": username, "password": password,
    })
    assert login_resp.status_code == 200, login_resp.text
    return login_resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_port_suggestions_requires_auth(client):
    """未登录访问被拒绝。"""
    resp = await client.get("/api/settings/port-suggestions", params={"count": 3})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_port_suggestions_sequential_skipping_used(client, monkeypatch):
    """从默认起始端口 10000 顺序分配，跳过已占用端口。"""
    monkeypatch.setattr(
        "app.api.settings.get_used_ports", lambda: {10000, 10002}
    )
    token = await _register_and_login(client, "portuser")

    resp = await client.get(
        "/api/settings/port-suggestions",
        params={"count": 3},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["ports"] == [10001, 10003, 10004]


@pytest.mark.asyncio
async def test_port_suggestions_count_validation(client):
    """count 超出 1-200 范围时返回 422。"""
    token = await _register_and_login(client, "portuser2")
    for count in (0, 201):
        resp = await client.get(
            "/api/settings/port-suggestions",
            params={"count": count},
            headers=_auth(token),
        )
        assert resp.status_code == 422, f"count={count} 应被拒绝"


@pytest.mark.asyncio
async def test_port_suggestions_respects_custom_start(client, monkeypatch):
    """管理员修改 service_port_start 后，建议从新起始端口分配。"""
    monkeypatch.setattr("app.api.settings.get_used_ports", lambda: set())
    # 首个注册用户为 admin
    token = await _register_and_login(client, "portadmin")

    resp = await client.put(
        "/api/settings",
        json={"service_port_start": 20000},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(
        "/api/settings/port-suggestions",
        params={"count": 2},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["ports"] == [20000, 20001]
