import base64
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import httpx

from app.providers.email.base import (
    EmailProvider,
    EmailProviderError,
    InboundReply,
    QuotaStatus,
    ReauthRequiredError,
    SendEmailRequest,
    SendEmailResult,
)
from app.providers.email.mime_utils import build_mime_message
from app.services import google_oauth

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

# Refresh a little before actual expiry so a send never races an expired token.
EXPIRY_SAFETY_MARGIN_SECONDS = 60


class GmailOAuthProvider(EmailProvider):
    """Sends via the Gmail API so mail appears in Sent and threads correctly.
    Reply detection (Phase 7) will use the same API's history/threads endpoints."""

    def __init__(
        self,
        credentials: dict,
        on_token_refreshed: Callable[[dict], Awaitable[None]] | None = None,
    ):
        self._credentials = credentials
        self._on_token_refreshed = on_token_refreshed

    async def _get_valid_access_token(self) -> str:
        expiry = self._credentials.get("token_expiry")
        access_token = self._credentials.get("access_token")

        if expiry and access_token:
            expires_at = datetime.fromisoformat(expiry)
            if expires_at > datetime.now(UTC) + timedelta(
                seconds=EXPIRY_SAFETY_MARGIN_SECONDS
            ):
                return access_token

        refresh_token = self._credentials.get("refresh_token")
        if not refresh_token:
            raise ReauthRequiredError("No refresh token stored for this account. Reconnect Gmail.")

        try:
            token_response = await google_oauth.refresh_access_token(refresh_token)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (400, 401):
                raise ReauthRequiredError(
                    "Gmail access was revoked or expired. Reconnect this account."
                ) from exc
            raise EmailProviderError(f"Token refresh failed: {exc}") from exc

        new_access_token = token_response["access_token"]
        expires_in = token_response.get("expires_in", 3600)
        new_expiry = (datetime.now(UTC) + timedelta(seconds=expires_in)).isoformat()

        self._credentials["access_token"] = new_access_token
        self._credentials["token_expiry"] = new_expiry

        if self._on_token_refreshed:
            await self._on_token_refreshed(dict(self._credentials))

        return new_access_token

    async def send(self, request: SendEmailRequest) -> SendEmailResult:
        access_token = await self._get_valid_access_token()
        mime_message, message_id = build_mime_message(request)

        raw = base64.urlsafe_b64encode(mime_message.as_bytes()).decode()
        payload: dict = {"raw": raw}
        if request.thread_id:
            payload["threadId"] = request.thread_id

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{GMAIL_API_BASE}/messages/send",
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
            )

        if response.status_code == 401:
            raise ReauthRequiredError("Gmail rejected the access token. Reconnect this account.")
        if response.status_code >= 400:
            raise EmailProviderError(f"Gmail send failed ({response.status_code}): {response.text}")

        body = response.json()
        return SendEmailResult(provider_message_id=body["id"], thread_id=body.get("threadId"))

    async def verify_credentials(self) -> bool:
        access_token = await self._get_valid_access_token()
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{GMAIL_API_BASE}/profile",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if response.status_code == 401:
            raise ReauthRequiredError("Gmail rejected the access token. Reconnect this account.")
        if response.status_code >= 400:
            raise EmailProviderError(f"Gmail profile check failed: {response.text}")
        return True

    async def fetch_replies_since(self, since: datetime) -> list[InboundReply]:
        return []

    async def get_quota_status(self) -> QuotaStatus:
        return QuotaStatus()
