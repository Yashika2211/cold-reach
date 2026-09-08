import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin
from app.models.enums import JobOpeningStatus, WorkMode

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.company import Company


class JobOpening(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "job_openings"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True, index=True
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    work_mode: Mapped[WorkMode] = mapped_column(
        Enum(WorkMode, name="work_mode"), nullable=False, default=WorkMode.unspecified
    )
    experience_range: Mapped[str | None] = mapped_column(String(128), nullable=True)
    batch_eligibility: Mapped[str | None] = mapped_column(String(255), nullable=True)
    salary_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    apply_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_board: Mapped[str | None] = mapped_column(String(128), nullable=True)
    posted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    discovered_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[JobOpeningStatus] = mapped_column(
        Enum(JobOpeningStatus, name="job_opening_status"),
        nullable=False,
        default=JobOpeningStatus.open,
    )

    company: Mapped["Company"] = relationship(back_populates="job_openings")
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="job_opening")

    def __repr__(self) -> str:
        return f"<JobOpening id={self.id} title={self.title!r}>"
