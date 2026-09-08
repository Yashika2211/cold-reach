import uuid

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class Company(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_band: Mapped[str | None] = mapped_column(String(64), nullable=True)
    careers_page_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    research_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    contacts: Mapped[list["Contact"]] = relationship(back_populates="company")
    job_openings: Mapped[list["JobOpening"]] = relationship(back_populates="company")

    def __repr__(self) -> str:
        return f"<Company id={self.id} name={self.name!r}>"
