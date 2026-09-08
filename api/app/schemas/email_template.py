import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EmailTemplateCreate(BaseModel):
    name: str
    subject_skeleton: str
    body_skeleton: str
    llm_instructions: str | None = None


class EmailTemplateUpdate(BaseModel):
    name: str | None = None
    subject_skeleton: str | None = None
    body_skeleton: str | None = None
    llm_instructions: str | None = None


class EmailTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    subject_skeleton: str
    body_skeleton: str
    llm_instructions: str | None
    created_at: datetime
    updated_at: datetime
