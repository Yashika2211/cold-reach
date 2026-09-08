import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin
from app.models.enums import ContactSource, ContactStatus, VerificationStatus


class Contact(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("normalized_email", name="uq_contacts_normalized_email"),)

    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True, index=True
    )

    linkedin_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    source: Mapped[ContactSource] = mapped_column(
        Enum(ContactSource, name="contact_source"), nullable=False, default=ContactSource.manual
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status"),
        nullable=False,
        default=VerificationStatus.unverified,
    )
    confidence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[ContactStatus] = mapped_column(
        Enum(ContactStatus, name="contact_status"), nullable=False, default=ContactStatus.new
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    company: Mapped["Company"] = relationship(back_populates="contacts")
    campaign_contacts: Mapped[list["CampaignContact"]] = relationship(back_populates="contact")

    def __repr__(self) -> str:
        return f"<Contact id={self.id} email={self.email!r}>"
