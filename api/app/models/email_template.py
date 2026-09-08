from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.campaign import Campaign


class EmailTemplate(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "email_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject_skeleton: Mapped[str] = mapped_column(Text, nullable=False)
    body_skeleton: Mapped[str] = mapped_column(Text, nullable=False)
    llm_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="email_template")

    def __repr__(self) -> str:
        return f"<EmailTemplate id={self.id} name={self.name!r}>"
