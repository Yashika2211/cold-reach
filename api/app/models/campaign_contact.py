import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin
from app.models.enums import CampaignContactStatus


class CampaignContact(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "campaign_contacts"
    __table_args__ = (
        UniqueConstraint("campaign_id", "contact_id", name="uq_campaign_contacts_campaign_contact"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False, index=True
    )

    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[CampaignContactStatus] = mapped_column(
        Enum(CampaignContactStatus, name="campaign_contact_status"),
        nullable=False,
        default=CampaignContactStatus.pending,
    )
    generated_email_history: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)

    campaign: Mapped["Campaign"] = relationship(back_populates="campaign_contacts")
    contact: Mapped["Contact"] = relationship(back_populates="campaign_contacts")
    email_messages: Mapped[list["EmailMessage"]] = relationship(back_populates="campaign_contact")

    def __repr__(self) -> str:
        return f"<CampaignContact id={self.id} campaign_id={self.campaign_id} contact_id={self.contact_id}>"
