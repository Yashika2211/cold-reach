import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompanyBase(BaseModel):
    name: str
    domain: str | None = None
    industry: str | None = None
    size_band: str | None = None
    careers_page_url: str | None = None
    location: str | None = None
    research_summary: str | None = None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    industry: str | None = None
    size_band: str | None = None
    careers_page_url: str | None = None
    location: str | None = None
    research_summary: str | None = None


class CompanyRead(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
