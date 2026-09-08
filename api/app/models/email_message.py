import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import BounceType

if TYPE_CHECKING:
    from app.models.campaign_contact import CampaignContact
    from app.models.sending_account import SendingAccount


class EmailMessage(UUIDPKMixin, TimestampMixin, Base):
    """Permanent, append-mostly record of one sent (or attempted) email. Never soft-deleted.

    campaign_contact_id is nullable to support standalone sends (Phase 3's manual send /
    connection-test flow, used before Campaign exists and as an ongoing "send test email"
    utility) alongside campaign-driven sends.
    """

    __tablename__ = "email_messages"

    campaign_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign_contacts.id"), nullable=True, index=True
    )
    sending_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sending_accounts.id"), nullable=False, index=True
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    to_email: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(998), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    provider_message_id: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    thread_id: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    open_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reply_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    bounce_type: Mapped[BounceType] = mapped_column(
        Enum(BounceType, name="bounce_type"), nullable=False, default=BounceType.none
    )
    bounce_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    campaign_contact: Mapped["CampaignContact | None"] = relationship(back_populates="email_messages")
    sending_account: Mapped["SendingAccount"] = relationship()

    def __repr__(self) -> str:
        return f"<EmailMessage id={self.id} step={self.step_number} subject={self.subject!r}>"
