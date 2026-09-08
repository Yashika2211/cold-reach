import uuid
from datetime import time as dt_time

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin
from app.models.enums import CampaignMode, CampaignStatus

# Default send window: Tue-Thu, 09:00-11:30 Asia/Kolkata. Weekdays: Mon=0 ... Sun=6.
DEFAULT_SEND_WINDOW_DAYS = [1, 2, 3]
DEFAULT_FOLLOW_UP_SCHEDULE_DAYS = [4, 9]


class Campaign(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    job_opening_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_openings.id"), nullable=True, index=True
    )
    target_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    resume_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resume_variants.id"), nullable=False
    )
    email_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_templates.id"), nullable=False
    )
    sending_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sending_accounts.id"), nullable=False
    )

    mode: Mapped[CampaignMode] = mapped_column(
        Enum(CampaignMode, name="campaign_mode"), nullable=False, default=CampaignMode.review_required
    )
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status"), nullable=False, default=CampaignStatus.draft
    )

    daily_cap: Mapped[int] = mapped_column(Integer, nullable=False, default=40)

    send_window_start_local: Mapped[dt_time] = mapped_column(
        Time, nullable=False, default=lambda: dt_time(9, 0)
    )
    send_window_end_local: Mapped[dt_time] = mapped_column(
        Time, nullable=False, default=lambda: dt_time(11, 30)
    )
    send_window_days: Mapped[list[int]] = mapped_column(
        JSONB, nullable=False, default=lambda: list(DEFAULT_SEND_WINDOW_DAYS)
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")

    follow_up_schedule_days: Mapped[list[int]] = mapped_column(
        JSONB, nullable=False, default=lambda: list(DEFAULT_FOLLOW_UP_SCHEDULE_DAYS)
    )

    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bounce_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    job_opening: Mapped["JobOpening"] = relationship(back_populates="campaigns")
    resume_variant: Mapped["ResumeVariant"] = relationship(back_populates="campaigns")
    email_template: Mapped["EmailTemplate"] = relationship(back_populates="campaigns")
    sending_account: Mapped["SendingAccount"] = relationship(back_populates="campaigns")
    campaign_contacts: Mapped[list["CampaignContact"]] = relationship(back_populates="campaign")

    def __repr__(self) -> str:
        return f"<Campaign id={self.id} name={self.name!r}>"
