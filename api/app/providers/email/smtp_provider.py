from datetime import datetime

import aiosmtplib

from app.providers.email.base import (
    EmailProvider,
    EmailProviderError,
    InboundReply,
    QuotaStatus,
    SendEmailRequest,
    SendEmailResult,
)
from app.providers.email.mime_utils import build_mime_message


class SmtpProvider(EmailProvider):
    """Standard SMTP with STARTTLS. Credentials: a Gmail app password works fine here,
    or any other SMTP host. Reply detection (Phase 7) will need a separate IMAP poller —
    SMTP alone can't observe the mailbox."""

    def __init__(self, credentials: dict):
        self.host: str = credentials["host"]
        self.port: int = int(credentials.get("port", 587))
        self.username: str = credentials["username"]
        self.password: str = credentials["password"]
        self.use_starttls: bool = credentials.get("use_starttls", True)

    async def send(self, request: SendEmailRequest) -> SendEmailResult:
        mime_message, message_id = build_mime_message(request)
        try:
            await aiosmtplib.send(
                mime_message,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=self.use_starttls,
            )
        except aiosmtplib.SMTPException as exc:
            raise EmailProviderError(f"SMTP send failed: {exc}") from exc

        return SendEmailResult(provider_message_id=message_id, thread_id=request.thread_id or message_id)

    async def verify_credentials(self) -> bool:
        try:
            smtp = aiosmtplib.SMTP(hostname=self.host, port=self.port, start_tls=self.use_starttls)
            await smtp.connect()
            await smtp.login(self.username, self.password)
            await smtp.quit()
        except aiosmtplib.SMTPException as exc:
            raise EmailProviderError(f"SMTP authentication failed: {exc}") from exc
        return True

    async def fetch_replies_since(self, since: datetime) -> list[InboundReply]:
        return []

    async def get_quota_status(self) -> QuotaStatus:
        return QuotaStatus()
