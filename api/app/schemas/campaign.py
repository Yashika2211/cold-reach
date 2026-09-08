import uuid
from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CampaignContactStatus, CampaignMode, CampaignStatus

MAX_DAILY_CAP = 150


class CampaignCreate(BaseModel):
    name: str
    target_description: str | None = None
    job_opening_id: uuid.UUID | None = None
    resume_variant_id: uuid.UUID
    email_template_id: uuid.UUID
    sending_account_id: uuid.UUID
    mode: CampaignMode = CampaignMode.review_required
    daily_cap: int = Field(default=40, ge=1, le=MAX_DAILY_CAP)
    send_window_start_local: time = time(9, 0)
    send_window_end_local: time = time(11, 30)
    send_window_days: list[int] = [1, 2, 3]
    timezone: str = "Asia/Kolkata"
    follow_up_schedule_days: list[int] = [4, 9]


class CampaignUpdate(BaseModel):
    name: str | None = None
    target_description: str | None = None
    status: CampaignStatus | None = None
    daily_cap: int | None = Field(default=None, ge=1, le=MAX_DAILY_CAP)
    send_window_start_local: time | None = None
    send_window_end_local: time | None = None
    send_window_days: list[int] | None = None
    timezone: str | None = None
    follow_up_schedule_days: list[int] | None = None


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    target_description: str | None
    job_opening_id: uuid.UUID | None
    resume_variant_id: uuid.UUID
    email_template_id: uuid.UUID
    sending_account_id: uuid.UUID
    mode: CampaignMode
    status: CampaignStatus
    daily_cap: int
    send_window_start_local: time
    send_window_end_local: time
    send_window_days: list[int]
    timezone: str
    follow_up_schedule_days: list[int]
    sent_count: int
    reply_count: int
    bounce_count: int
    created_at: datetime
    updated_at: datetime


class AddContactsRequest(BaseModel):
    contact_ids: list[uuid.UUID]


class AddContactsResponse(BaseModel):
    added: int
    skipped_existing: int


class CampaignFunnel(BaseModel):
    total: int
    by_status: dict[str, int]


class EmailDraft(BaseModel):
    step_number: int
    subject: str
    body: str
    personalization_rationale: str
    needs_more_context: bool
    quality_gate: dict
    source: str
    steering_note: str | None = None
    created_at: datetime


class CampaignContactRead(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    contact_id: uuid.UUID
    contact_email: str
    contact_name: str
    current_step: int
    status: CampaignContactStatus
    current_draft: EmailDraft | None
    created_at: datetime
    updated_at: datetime


class ReviewQueueResponse(BaseModel):
    campaign_contact: CampaignContactRead | None
    remaining: int


class RegenerateRequest(BaseModel):
    steering_note: str | None = None


class HandEditRequest(BaseModel):
    subject: str
    body: str
