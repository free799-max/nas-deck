import pytest


@pytest.mark.asyncio
async def test_register_user(client):
    resp = await client.post("/api/auth/register", json={
        "username": "admin",
        "password": "admin123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "admin"
    assert "id" in data
    assert "hashed_password" not in data  # 不暴露密码


@pytest.mark.asyncio
async def test_register_duplicate_user(client):
    await client.post("/api/auth/register", json={
        "username": "admin", "password": "admin123",
    })
    resp = await client.post("/api/auth/register", json={
        "username": "admin", "password": "admin123",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login(client):
    await client.post("/api/auth/register", json={
        "username": "admin", "password": "admin123",
    })
    resp = await client.post("/api/auth/login", json={
        "username": "admin", "password": "admin123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/auth/register", json={
        "username": "admin", "password": "admin123",
    })
    resp = await client.post("/api/auth/login", json={
        "username": "admin", "password": "wrong",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user(client):
    await client.post("/api/auth/register", json={
        "username": "admin", "password": "admin123",
    })
    login_resp = await client.post("/api/auth/login", json={
        "username": "admin", "password": "admin123",
    })
    token = login_resp.json()["access_token"]
    resp = await client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {token}",
    })
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(client):
    resp = await client.get("/api/auth/me", headers={
        "Authorization": "Bearer invalid-token",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_no_token(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 403  # HTTPBearer returns 403 when no token provided
