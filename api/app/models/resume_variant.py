from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.campaign import Campaign


class ResumeVariant(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "resume_variants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_family: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    pdf_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    positioning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    highlight_projects: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="resume_variant")

    def __repr__(self) -> str:
        return f"<ResumeVariant id={self.id} name={self.name!r}>"
