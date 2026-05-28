import pytest


async def get_auth_header(client):
    await client.post("/api/auth/register", json={"username": "admin", "password": "admin123"})
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_available_plugins(client):
    headers = await get_auth_header(client)
    resp = await client.get("/api/plugins/available", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_plugin_instance(client):
    headers = await get_auth_header(client)
    resp = await client.post("/api/plugins/instances", headers=headers, json={
        "plugin_name": "jellyfin",
        "display_name": "My Jellyfin",
        "config": {"url": "http://localhost:8096", "api_key": "test"},
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["plugin_name"] == "jellyfin"
    assert data["display_name"] == "My Jellyfin"


@pytest.mark.asyncio
async def test_list_plugin_instances(client):
    headers = await get_auth_header(client)
    await client.post("/api/plugins/instances", headers=headers, json={
        "plugin_name": "jellyfin",
        "display_name": "My Jellyfin",
        "config": {},
    })
    resp = await client.get("/api/plugins/instances", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_plugin_instance(client):
    headers = await get_auth_header(client)
    create_resp = await client.post("/api/plugins/instances", headers=headers, json={
        "plugin_name": "jellyfin",
        "display_name": "My Jellyfin",
        "config": {},
    })
    instance_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/plugins/instances/{instance_id}", headers=headers)
    assert resp.status_code == 204
