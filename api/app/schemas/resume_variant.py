import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ResumeVariantCreate(BaseModel):
    name: str
    role_family: str | None = None
    positioning_summary: str | None = None
    highlight_projects: list[str] = []
    is_default: bool = False


class ResumeVariantUpdate(BaseModel):
    name: str | None = None
    role_family: str | None = None
    positioning_summary: str | None = None
    highlight_projects: list[str] | None = None
    is_default: bool | None = None


class ResumeVariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    role_family: str | None
    positioning_summary: str | None
    highlight_projects: list[str]
    is_default: bool
    has_pdf: bool = False
    created_at: datetime
    updated_at: datetime
