import base64
from datetime import UTC, datetime, timedelta

import aiosmtplib
import httpx
import pytest
import respx

from app.providers.email.base import (
    EmailProviderError,
    ReauthRequiredError,
    SendEmailRequest,
)
from app.providers.email.gmail_oauth_provider import GmailOAuthProvider
from app.providers.email.smtp_provider import SmtpProvider

SAMPLE_REQUEST = SendEmailRequest(
    to_email="recipient@example.com",
    subject="Hello",
    body_text="Hi there.",
    from_email="me@gmail.com",
    from_name="Me",
    reply_to="me@gmail.com",
)


@pytest.mark.asyncio
async def test_smtp_provider_send_calls_aiosmtplib(monkeypatch):
    captured = {}

    async def fake_send(message, **kwargs):
        captured["message"] = message
        captured["kwargs"] = kwargs
        return None, {}

    monkeypatch.setattr(aiosmtplib, "send", fake_send)

    provider = SmtpProvider(
        {"host": "smtp.gmail.com", "port": 587, "username": "me@gmail.com", "password": "pw"}
    )
    result = await provider.send(SAMPLE_REQUEST)

    assert captured["kwargs"]["hostname"] == "smtp.gmail.com"
    assert captured["kwargs"]["username"] == "me@gmail.com"
    assert captured["message"]["Subject"] == "Hello"
    assert captured["message"]["From"] == "Me <me@gmail.com>"
    assert result.provider_message_id  # a Message-ID was generated


@pytest.mark.asyncio
async def test_smtp_provider_verify_credentials_success(monkeypatch):
    class FakeSmtp:
        def __init__(self, **kwargs):
            pass

        async def connect(self):
            pass

        async def login(self, username, password):
            pass

        async def quit(self):
            pass

    monkeypatch.setattr(aiosmtplib, "SMTP", FakeSmtp)

    provider = SmtpProvider({"host": "h", "username": "u", "password": "p"})
    assert await provider.verify_credentials() is True


@pytest.mark.asyncio
async def test_smtp_provider_verify_credentials_failure_raises(monkeypatch):
    class FakeSmtp:
        def __init__(self, **kwargs):
            pass

        async def connect(self):
            pass

        async def login(self, username, password):
            raise aiosmtplib.SMTPAuthenticationError(535, "bad credentials")

        async def quit(self):
            pass

    monkeypatch.setattr(aiosmtplib, "SMTP", FakeSmtp)

    provider = SmtpProvider({"host": "h", "username": "u", "password": "wrong"})
    with pytest.raises(EmailProviderError):
        await provider.verify_credentials()


@pytest.mark.asyncio
@respx.mock
async def test_gmail_provider_sends_via_api_with_valid_token():
    respx.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send").mock(
        return_value=httpx.Response(200, json={"id": "gmail-msg-1", "threadId": "thread-1"})
    )

    credentials = {
        "access_token": "still-valid-token",
        "token_expiry": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "refresh_token": "refresh-abc",
        "gmail_address": "me@gmail.com",
    }
    provider = GmailOAuthProvider(credentials)
    result = await provider.send(SAMPLE_REQUEST)

    assert result.provider_message_id == "gmail-msg-1"
    assert result.thread_id == "thread-1"

    sent_request = respx.calls.last.request
    import json

    payload = json.loads(sent_request.content)
    raw_bytes = base64.urlsafe_b64decode(payload["raw"])
    assert b"Hello" in raw_bytes
    assert b"me@gmail.com" in raw_bytes


@pytest.mark.asyncio
@respx.mock
async def test_gmail_provider_refreshes_expired_token():
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(
            200, json={"access_token": "new-token", "expires_in": 3600}
        )
    )
    send_route = respx.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send").mock(
        return_value=httpx.Response(200, json={"id": "m1", "threadId": "t1"})
    )

    credentials = {
        "access_token": "expired-token",
        "token_expiry": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        "refresh_token": "refresh-abc",
        "gmail_address": "me@gmail.com",
    }

    refreshed = {}

    async def on_refresh(new_creds):
        refreshed.update(new_creds)

    provider = GmailOAuthProvider(credentials, on_token_refreshed=on_refresh)
    await provider.send(SAMPLE_REQUEST)

    assert send_route.calls.last.request.headers["Authorization"] == "Bearer new-token"
    assert refreshed["access_token"] == "new-token"


@pytest.mark.asyncio
@respx.mock
async def test_gmail_provider_raises_reauth_required_when_refresh_token_revoked():
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(400, json={"error": "invalid_grant"})
    )

    credentials = {
        "access_token": "expired-token",
        "token_expiry": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        "refresh_token": "revoked-refresh-token",
        "gmail_address": "me@gmail.com",
    }
    provider = GmailOAuthProvider(credentials)

    with pytest.raises(ReauthRequiredError):
        await provider.send(SAMPLE_REQUEST)


@pytest.mark.asyncio
@respx.mock
async def test_gmail_provider_raises_reauth_required_on_401_from_send():
    credentials = {
        "access_token": "still-valid-token",
        "token_expiry": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "refresh_token": "refresh-abc",
        "gmail_address": "me@gmail.com",
    }
    respx.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send").mock(
        return_value=httpx.Response(401, json={"error": "unauthorized"})
    )

    provider = GmailOAuthProvider(credentials)
    with pytest.raises(ReauthRequiredError):
        await provider.send(SAMPLE_REQUEST)
