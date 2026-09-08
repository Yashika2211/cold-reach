import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import SuppressionReason, SuppressionSource


class SuppressionCreate(BaseModel):
    email: EmailStr
    reason: SuppressionReason = SuppressionReason.manual_block


class SuppressionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    normalized_email: str
    reason: SuppressionReason
    source: SuppressionSource
    created_at: datetime
