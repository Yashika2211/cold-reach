import pytest

from app.providers.email.base import EmailProviderError, ReauthRequiredError


@pytest.mark.asyncio
async def test_create_smtp_account_hides_credentials_in_response(auth_client):
    response = await auth_client.post(
        "/sending-accounts",
        json={
            "display_name": "My Gmail (SMTP)",
            "from_address": "me@gmail.com",
            "provider_type": "smtp",
            "daily_cap": 40,
            "smtp_credentials": {
                "host": "smtp.gmail.com",
                "port": 587,
                "username": "me@gmail.com",
                "password": "super-secret-app-password",
            },
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["from_address"] == "me@gmail.com"
    assert "password" not in str(body)
    assert "super-secret-app-password" not in str(body)
    assert "encrypted_credentials" not in body


@pytest.mark.asyncio
async def test_daily_cap_ceiling_enforced(auth_client):
    response = await auth_client.post(
        "/sending-accounts",
        json={
            "display_name": "Too Big",
            "from_address": "me@gmail.com",
            "provider_type": "smtp",
            "daily_cap": 151,
            "smtp_credentials": {"host": "smtp.gmail.com", "username": "a", "password": "b"},
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cannot_create_gmail_oauth_account_directly(auth_client):
    response = await auth_client.post(
        "/sending-accounts",
        json={
            "display_name": "Gmail",
            "from_address": "me@gmail.com",
            "provider_type": "gmail_oauth",
            "daily_cap": 40,
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_crud_lifecycle(auth_client):
    create_resp = await auth_client.post(
        "/sending-accounts",
        json={
            "display_name": "Test Account",
            "from_address": "test@example.com",
            "provider_type": "smtp",
            "daily_cap": 30,
            "smtp_credentials": {"host": "smtp.example.com", "username": "u", "password": "p"},
        },
    )
    account_id = create_resp.json()["id"]

    get_resp = await auth_client.get(f"/sending-accounts/{account_id}")
    assert get_resp.status_code == 200

    patch_resp = await auth_client.patch(f"/sending-accounts/{account_id}", json={"daily_cap": 25})
    assert patch_resp.json()["daily_cap"] == 25

    delete_resp = await auth_client.delete(f"/sending-accounts/{account_id}")
    assert delete_resp.status_code == 204

    missing_resp = await auth_client.get(f"/sending-accounts/{account_id}")
    assert missing_resp.status_code == 404


@pytest.mark.asyncio
async def test_connection_test_success(auth_client, smtp_sending_account, monkeypatch):
    class OkProvider:
        async def verify_credentials(self):
            return True

    monkeypatch.setattr(
        "app.api.routes.sending_accounts.build_provider", lambda account, db=None: OkProvider()
    )

    response = await auth_client.post(f"/sending-accounts/{smtp_sending_account.id}/test")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "detail": None, "needs_reauth": False}


@pytest.mark.asyncio
async def test_connection_test_reports_failure(auth_client, smtp_sending_account, monkeypatch):
    class FailingProvider:
        async def verify_credentials(self):
            raise EmailProviderError("bad password")

    monkeypatch.setattr(
        "app.api.routes.sending_accounts.build_provider", lambda account, db=None: FailingProvider()
    )

    response = await auth_client.post(f"/sending-accounts/{smtp_sending_account.id}/test")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "bad password" in body["detail"]


@pytest.mark.asyncio
async def test_connection_test_flags_reauth_needed(auth_client, smtp_sending_account, monkeypatch):
    class RevokedProvider:
        async def verify_credentials(self):
            raise ReauthRequiredError("revoked")

    monkeypatch.setattr(
        "app.api.routes.sending_accounts.build_provider", lambda account, db=None: RevokedProvider()
    )

    response = await auth_client.post(f"/sending-accounts/{smtp_sending_account.id}/test")
    body = response.json()
    assert body["ok"] is False
    assert body["needs_reauth"] is True


@pytest.mark.asyncio
async def test_send_test_endpoint_blocks_suppressed_recipient(auth_client, smtp_sending_account):
    await auth_client.post("/suppression", json={"email": "blocked@example.com"})

    response = await auth_client.post(
        f"/sending-accounts/{smtp_sending_account.id}/send-test",
        json={"to_email": "blocked@example.com"},
    )
    assert response.status_code == 403
