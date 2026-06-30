"""自动化组合模板 API 集成测试。"""

import pytest


@pytest.mark.asyncio
async def test_list_orchestrations_requires_auth(client):
    """未认证时返回 403（HTTPBearer 默认行为）。"""
    resp = await client.get("/api/orchestrations?category=media")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_orchestration_api_returns_composition_fields(client):
    """认证后返回的组合模板包含 app_composition 和 shared_config_schema。"""
    # 注册并登录
    await client.post("/api/auth/register", json={
        "username": "autotest",
        "password": "autotest123",
    })
    login_resp = await client.post("/api/auth/login", json={
        "username": "autotest",
        "password": "autotest123",
    })
    token = login_resp.json()["data"]["access_token"]

    resp = await client.get("/api/orchestrations?category=media", headers={
        "Authorization": f"Bearer {token}",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    # 如果数据库中有 media 分类的编排，验证字段结构
    for item in data:
        assert "app_composition" in item
        assert "shared_config_schema" in item
        assert "yaml_template" not in item
        assert "config_schema" not in item
