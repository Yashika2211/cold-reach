from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EmailAttachment:
    filename: str
    content: bytes
    mime_type: str = "application/pdf"


@dataclass
class SendEmailRequest:
    to_email: str
    subject: str
    body_text: str
    from_email: str
    from_name: str
    to_name: str | None = None
    reply_to: str | None = None
    # For a follow-up in an existing thread (Phase 7).
    thread_id: str | None = None
    in_reply_to_message_id: str | None = None
    references: list[str] = field(default_factory=list)
    attachments: list[EmailAttachment] = field(default_factory=list)


@dataclass
class SendEmailResult:
    provider_message_id: str
    thread_id: str | None = None


@dataclass
class QuotaStatus:
    sent_today: int | None = None
    daily_limit: int | None = None
    remaining: int | None = None


@dataclass
class InboundReply:
    provider_message_id: str
    thread_id: str | None
    in_reply_to_message_id: str | None
    from_email: str
    subject: str
    received_at: datetime
    is_auto_response: bool = False


class EmailProviderError(Exception):
    """Raised when a provider operation fails in a way the caller should surface."""


class ReauthRequiredError(EmailProviderError):
    """The account's stored credentials (typically an OAuth refresh token) were
    revoked or expired. The UI must prompt the user to reconnect this account."""


class EmailProvider(ABC):
    """Every concrete provider sends as the SendingAccount's own address only —
    from_email/reply_to on the request are never allowed to be spoofed by a caller
    other than the account's own configured identity (enforced by the caller, not
    the provider, but every implementation must send exactly what it's given here)."""

    @abstractmethod
    async def send(self, request: SendEmailRequest) -> SendEmailResult: ...

    @abstractmethod
    async def verify_credentials(self) -> bool: ...

    @abstractmethod
    async def fetch_replies_since(self, since: datetime) -> list[InboundReply]:
        """Reply detection lands in Phase 7. Implementations may return an empty list
        until then, but must not raise NotImplementedError so callers don't need to
        special-case providers."""

    @abstractmethod
    async def get_quota_status(self) -> QuotaStatus: ...
