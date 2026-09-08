import pytest

from tests.conftest import ADMIN_EMAIL


@pytest.mark.asyncio
async def test_me_requires_auth(client, admin_user):
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_password(client, admin_user):
    response = await client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong-password"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_then_me(auth_client):
    response = await auth_client.get("/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == ADMIN_EMAIL


@pytest.mark.asyncio
async def test_logout_clears_session(auth_client):
    response = await auth_client.post("/auth/logout")
    assert response.status_code == 200

    response = await auth_client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_requires_auth(client):
    response = await client.get("/companies")
    assert response.status_code == 401
