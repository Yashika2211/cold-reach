import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class EventLog(UUIDPKMixin, TimestampMixin, Base):
    """Append-only audit trail of every state transition. Never updated or deleted."""

    __tablename__ = "event_logs"

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    def __repr__(self) -> str:
        return f"<EventLog id={self.id} entity_type={self.entity_type} event_type={self.event_type}>"
