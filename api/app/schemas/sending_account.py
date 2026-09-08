import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SendingAccountProvider

# 150/day is the absolute ceiling from the brief (§2.2) — the API refuses to exceed it,
# same as the UI.
MAX_DAILY_CAP = 150


class SmtpCredentials(BaseModel):
    host: str
    port: int = 587
    username: str
    password: str
    use_starttls: bool = True


class ApiProviderCredentials(BaseModel):
    vendor: str  # "resend" | "sendgrid"
    api_key: str


class SendingAccountCreate(BaseModel):
    display_name: str
    from_address: str
    provider_type: SendingAccountProvider
    daily_cap: int = Field(default=40, ge=1, le=MAX_DAILY_CAP)
    smtp_credentials: SmtpCredentials | None = None
    api_credentials: ApiProviderCredentials | None = None


class SendingAccountUpdate(BaseModel):
    display_name: str | None = None
    daily_cap: int | None = Field(default=None, ge=1, le=MAX_DAILY_CAP)
    is_active: bool | None = None


class SendingAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    from_address: str
    provider_type: SendingAccountProvider
    daily_cap: int
    health_metrics: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ConnectionTestResult(BaseModel):
    ok: bool
    detail: str | None = None
    needs_reauth: bool = False


class SendTestEmailRequest(BaseModel):
    to_email: str
    subject: str = "ColdReach test email"
    body_text: str = (
        "This is a test email from ColdReach, confirming this sending account works.\n\n"
        "If you're reading this in your inbox, the connection is good."
    )
    resume_variant_id: uuid.UUID | None = None


class SendTestEmailResponse(BaseModel):
    email_message_id: uuid.UUID
    provider_message_id: str
    sent_at: datetime
