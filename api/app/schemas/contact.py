import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import ContactSource, ContactStatus, VerificationStatus


class ContactBase(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr
    title: str | None = None
    company_id: uuid.UUID | None = None
    linkedin_url: str | None = None
    notes: str | None = None


class ContactCreate(ContactBase):
    source: ContactSource = ContactSource.manual


class ContactUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    title: str | None = None
    company_id: uuid.UUID | None = None
    linkedin_url: str | None = None
    notes: str | None = None
    status: ContactStatus | None = None


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str | None
    last_name: str | None
    email: str
    normalized_email: str
    title: str | None
    company_id: uuid.UUID | None
    company_name: str | None = None
    linkedin_url: str | None
    notes: str | None
    source: ContactSource
    verification_status: VerificationStatus
    confidence_score: int | None
    status: ContactStatus
    is_suppressed: bool = False
    created_at: datetime
    updated_at: datetime
