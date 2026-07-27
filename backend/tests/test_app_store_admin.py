"""应用商店应用创建/编辑/删除管理接口测试。"""

import pytest

from app.config import settings

# 合法的最小应用定义
VALID_YAML_TEMPLATE = """services:
  app:
    image: {{ image }}
    container_name: {{ project_name }}
"""

VALID_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "port": {"type": "integer", "default": 8080},
    },
}

VALID_APP_PAYLOAD = {
    "name": "testapp",
    "display_name": "Test App",
    "description": "测试应用",
    "category": "other",
    "tags": ["test"],
    "image": "example/image",
    "config_schema": VALID_CONFIG_SCHEMA,
    "yaml_template": VALID_YAML_TEMPLATE,
}


async def _register_and_login(client, username: str, password: str = "pass123456") -> str:
    """注册用户并登录，返回 access_token。"""
    await client.post("/api/auth/register", json={
        "username": username, "password": password,
    })
    login_resp = await client.post("/api/auth/login", json={
        "username": username, "password": password,
    })
    return login_resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _mark_builtin(client, name: str) -> None:
    """通过测试数据库会话将应用标记为内置（is_builtin 不开放 API 修改）。"""
    from app.database import get_db
    from app.models.app_store import App
    from sqlalchemy import update

    get_test_db = client._transport.app.dependency_overrides[get_db]
    async for db in get_test_db():
        await db.execute(update(App).where(App.name == name).values(is_builtin=True))
        await db.commit()
        break


@pytest.mark.asyncio
async def test_create_app_success(client):
    """管理员可成功创建应用。"""
    token = await _register_and_login(client, "admin")  # 第一个用户为 admin
    resp = await client.post("/api/apps", json=VALID_APP_PAYLOAD, headers=_auth(token))
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "testapp"
    assert data["display_name"] == "Test App"
    assert data["is_builtin"] is False

    # 创建后可通过详情接口查询
    detail = await client.get("/api/apps/testapp", headers=_auth(token))
    assert detail.status_code == 200
    assert detail.json()["data"]["name"] == "testapp"


@pytest.mark.asyncio
async def test_create_app_duplicate_name(client):
    """重复 name 创建返回 409。"""
    token = await _register_and_login(client, "admin")
    await client.post("/api/apps", json=VALID_APP_PAYLOAD, headers=_auth(token))
    resp = await client.post("/api/apps", json=VALID_APP_PAYLOAD, headers=_auth(token))
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_app_invalid_name(client):
    """非法 name 格式返回 400。"""
    token = await _register_and_login(client, "admin")
    payload = {**VALID_APP_PAYLOAD, "name": "Invalid Name!"}
    resp = await client.post("/api/apps", json=payload, headers=_auth(token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_app_invalid_template(client):
    """yaml_template 渲染失败返回 400。"""
    token = await _register_and_login(client, "admin")
    payload = {**VALID_APP_PAYLOAD, "yaml_template": "services:\n  app:\n    image: {{ unclosed"}
    resp = await client.post("/api/apps", json=payload, headers=_auth(token))
    assert resp.status_code == 400
    assert "渲染失败" in resp.json()["message"]


@pytest.mark.asyncio
async def test_create_app_invalid_config_schema(client):
    """config_schema 默认值无法通过校验时返回 400。"""
    token = await _register_and_login(client, "admin")
    payload = {
        **VALID_APP_PAYLOAD,
        "config_schema": {
            "type": "object",
            "properties": {"port": {"type": "integer", "default": "not-a-number"}},
        },
    }
    resp = await client.post("/api/apps", json=payload, headers=_auth(token))
    assert resp.status_code == 400
    assert "config_schema" in resp.json()["message"]


@pytest.mark.asyncio
async def test_create_app_forbidden_for_normal_user(client):
    """普通用户创建应用返回 403。"""
    await _register_and_login(client, "admin")
    user_token = await _register_and_login(client, "normaluser")
    resp = await client.post("/api/apps", json=VALID_APP_PAYLOAD, headers=_auth(user_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_app_success(client):
    """管理员可更新应用字段。"""
    token = await _register_and_login(client, "admin")
    await client.post("/api/apps", json=VALID_APP_PAYLOAD, headers=_auth(token))

    resp = await client.put("/api/apps/testapp", json={
        "display_name": "Updated App",
        "description": "更新后的描述",
        "version": "2.0.0",
    }, headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["display_name"] == "Updated App"
    assert data["description"] == "更新后的描述"
    assert data["version"] == "2.0.0"


@pytest.mark.asyncio
async def test_update_app_invalid_template(client):
    """更新为非法模板时返回 400，原数据不受影响。"""
    token = await _register_and_login(client, "admin")
    await client.post("/api/apps", json=VALID_APP_PAYLOAD, headers=_auth(token))

    resp = await client.put("/api/apps/testapp", json={
        "yaml_template": "services:\n  app:\n    image: {{ broken",
    }, headers=_auth(token))
    assert resp.status_code == 400

    detail = await client.get("/api/apps/testapp", headers=_auth(token))
    assert detail.json()["data"]["name"] == "testapp"


@pytest.mark.asyncio
async def test_update_app_not_found(client):
    """更新不存在的应用返回 404。"""
    token = await _register_and_login(client, "admin")
    resp = await client.put("/api/apps/nonexistent", json={
        "display_name": "X",
    }, headers=_auth(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_app_success(client):
    """管理员可删除非内置且无实例的应用。"""
    token = await _register_and_login(client, "admin")
    await client.post("/api/apps", json=VALID_APP_PAYLOAD, headers=_auth(token))

    resp = await client.delete("/api/apps/testapp", headers=_auth(token))
    assert resp.status_code == 204

    detail = await client.get("/api/apps/testapp", headers=_auth(token))
    assert detail.status_code == 404


@pytest.mark.asyncio
async def test_delete_builtin_app_forbidden(client):
    """内置应用禁止删除。"""
    token = await _register_and_login(client, "admin")
    await client.post("/api/apps", json=VALID_APP_PAYLOAD, headers=_auth(token))

    # 将应用标记为内置（模拟内置应用数据修正场景）
    await _mark_builtin(client, "testapp")

    resp = await client.delete("/api/apps/testapp", headers=_auth(token))
    assert resp.status_code == 400
    assert "内置应用" in resp.json()["message"]


@pytest.mark.asyncio
async def test_delete_app_forbidden_for_normal_user(client):
    """普通用户删除应用返回 403。"""
    admin_token = await _register_and_login(client, "admin")
    await client.post("/api/apps", json=VALID_APP_PAYLOAD, headers=_auth(admin_token))
    user_token = await _register_and_login(client, "normaluser")
    resp = await client.delete("/api/apps/testapp", headers=_auth(user_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_preview_template(client):
    """未落库模板预览：成功返回渲染 YAML，失败返回错误。"""
    token = await _register_and_login(client, "admin")

    ok_resp = await client.post("/api/apps/preview-template", json={
        "yaml_template": VALID_YAML_TEMPLATE,
        "config_schema": VALID_CONFIG_SCHEMA,
        "image": "example/image",
    }, headers=_auth(token))
    assert ok_resp.status_code == 200
    data = ok_resp.json()["data"]
    assert data["error"] is None
    assert "example/image" in data["yaml"]

    bad_resp = await client.post("/api/apps/preview-template", json={
        "yaml_template": "services: [{{ broken",
        "config_schema": {},
    }, headers=_auth(token))
    assert bad_resp.status_code == 200
    assert bad_resp.json()["data"]["error"] is not None


@pytest.mark.asyncio
async def test_upload_and_get_app_icon(client, tmp_path, monkeypatch):
    """上传图标后可匿名读取，app.icon 更新为后端图标接口。"""
    monkeypatch.setattr(settings, "APP_ICON_DIR", str(tmp_path))

    token = await _register_and_login(client, "admin")
    await client.post("/api/apps", json=VALID_APP_PAYLOAD, headers=_auth(token))

    svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    resp = await client.post(
        "/api/apps/testapp/icon",
        files={"file": ("icon.svg", svg_content, "image/svg+xml")},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["icon"] == "/api/apps/testapp/icon"
    assert (tmp_path / "testapp.svg").read_bytes() == svg_content

    # 匿名可读取（<img> 标签无法携带 token）
    icon_resp = await client.get("/api/apps/testapp/icon")
    assert icon_resp.status_code == 200
    assert icon_resp.content == svg_content


@pytest.mark.asyncio
async def test_upload_icon_invalid_ext(client, tmp_path, monkeypatch):
    """不支持的图标格式返回 400。"""
    monkeypatch.setattr(settings, "APP_ICON_DIR", str(tmp_path))

    token = await _register_and_login(client, "admin")
    await client.post("/api/apps", json=VALID_APP_PAYLOAD, headers=_auth(token))

    resp = await client.post(
        "/api/apps/testapp/icon",
        files={"file": ("icon.exe", b"MZ", "application/octet-stream")},
        headers=_auth(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_icon_not_found(client, tmp_path, monkeypatch):
    """未上传图标时读取返回 404。"""
    monkeypatch.setattr(settings, "APP_ICON_DIR", str(tmp_path))
    resp = await client.get("/api/apps/nonexistent/icon")
    assert resp.status_code == 404
