from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import SuppressionReason, SuppressionSource


class SuppressionEntry(UUIDPKMixin, TimestampMixin, Base):
    """Global suppression list. Checked before every single send, regardless of campaign."""

    __tablename__ = "suppression_entries"

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    reason: Mapped[SuppressionReason] = mapped_column(
        Enum(SuppressionReason, name="suppression_reason"), nullable=False
    )
    source: Mapped[SuppressionSource] = mapped_column(
        Enum(SuppressionSource, name="suppression_source"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<SuppressionEntry id={self.id} email={self.email!r} reason={self.reason}>"
