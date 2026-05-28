import pytest


async def setup_auth_and_instance(client):
    await client.post("/api/auth/register", json={"username": "admin", "password": "admin123"})
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    inst_resp = await client.post("/api/plugins/instances", headers=headers, json={
        "plugin_name": "jellyfin",
        "display_name": "My Jellyfin",
        "config": {},
    })
    return headers, inst_resp.json()["id"]


@pytest.mark.asyncio
async def test_create_subscription(client):
    headers, instance_id = await setup_auth_and_instance(client)
    resp = await client.post("/api/subscriptions", headers=headers, json={
        "instance_id": instance_id,
        "item_id": "movie-123",
        "item_title": "Test Movie",
        "item_meta": {"year": 2026},
    })
    assert resp.status_code == 201
    assert resp.json()["item_title"] == "Test Movie"


@pytest.mark.asyncio
async def test_list_subscriptions(client):
    headers, instance_id = await setup_auth_and_instance(client)
    await client.post("/api/subscriptions", headers=headers, json={
        "instance_id": instance_id,
        "item_id": "movie-123",
        "item_title": "Test Movie",
        "item_meta": {},
    })
    resp = await client.get("/api/subscriptions", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_subscription(client):
    headers, instance_id = await setup_auth_and_instance(client)
    create_resp = await client.post("/api/subscriptions", headers=headers, json={
        "instance_id": instance_id,
        "item_id": "movie-123",
        "item_title": "Test Movie",
        "item_meta": {},
    })
    sub_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/subscriptions/{sub_id}", headers=headers)
    assert resp.status_code == 204
