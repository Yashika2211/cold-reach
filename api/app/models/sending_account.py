from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin
from app.models.enums import SendingAccountProvider

if TYPE_CHECKING:
    from app.models.campaign import Campaign


class SendingAccount(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "sending_accounts"

    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    from_address: Mapped[str] = mapped_column(String(320), nullable=False)
    provider_type: Mapped[SendingAccountProvider] = mapped_column(
        Enum(SendingAccountProvider, name="sending_account_provider"), nullable=False
    )
    encrypted_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    daily_cap: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    health_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="sending_account")

    def __repr__(self) -> str:
        return f"<SendingAccount id={self.id} from_address={self.from_address!r}>"
