from datetime import datetime

import httpx

from app.providers.email.base import (
    EmailProvider,
    EmailProviderError,
    InboundReply,
    QuotaStatus,
    SendEmailRequest,
    SendEmailResult,
)

RESEND_ENDPOINT = "https://api.resend.com/emails"
SENDGRID_ENDPOINT = "https://api.sendgrid.com/v3/mail/send"


class ApiProvider(EmailProvider):
    """Resend or SendGrid via their REST APIs. Demonstrates the abstraction, but is
    NOT the recommended path for cold outreach: most transactional ESPs prohibit this
    use case in their terms of service, and shared-IP sending reputation gives poor
    inbox placement at this volume. The UI must show a persistent warning wherever
    this provider type is selectable."""

    def __init__(self, credentials: dict):
        self.vendor: str = credentials["vendor"]  # "resend" | "sendgrid"
        self.api_key: str = credentials["api_key"]
        if self.vendor not in ("resend", "sendgrid"):
            raise EmailProviderError(f"Unknown API provider vendor: {self.vendor}")

    async def send(self, request: SendEmailRequest) -> SendEmailResult:
        if self.vendor == "resend":
            return await self._send_resend(request)
        return await self._send_sendgrid(request)

    async def _send_resend(self, request: SendEmailRequest) -> SendEmailResult:
        payload = {
            "from": f"{request.from_name} <{request.from_email}>",
            "to": [request.to_email],
            "subject": request.subject,
            "text": request.body_text,
        }
        if request.reply_to:
            payload["reply_to"] = request.reply_to

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                RESEND_ENDPOINT,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
        if response.status_code >= 400:
            raise EmailProviderError(f"Resend send failed ({response.status_code}): {response.text}")

        return SendEmailResult(provider_message_id=response.json()["id"])

    async def _send_sendgrid(self, request: SendEmailRequest) -> SendEmailResult:
        payload = {
            "personalizations": [{"to": [{"email": request.to_email}]}],
            "from": {"email": request.from_email, "name": request.from_name},
            "subject": request.subject,
            "content": [{"type": "text/plain", "value": request.body_text}],
        }
        if request.reply_to:
            payload["reply_to"] = {"email": request.reply_to}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                SENDGRID_ENDPOINT,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
        if response.status_code >= 400:
            raise EmailProviderError(f"SendGrid send failed ({response.status_code}): {response.text}")

        message_id = response.headers.get("X-Message-Id", "")
        return SendEmailResult(provider_message_id=message_id)

    async def verify_credentials(self) -> bool:
        if self.vendor == "resend":
            url = "https://api.resend.com/domains"
        else:
            url = "https://api.sendgrid.com/v3/user/account"

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {self.api_key}"})

        if response.status_code >= 400:
            raise EmailProviderError(f"{self.vendor} credential check failed: {response.text}")
        return True

    async def fetch_replies_since(self, since: datetime) -> list[InboundReply]:
        return []

    async def get_quota_status(self) -> QuotaStatus:
        return QuotaStatus()
