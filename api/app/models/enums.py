import enum


class ContactSource(str, enum.Enum):
    csv = "csv"
    enriched = "enriched"
    manual = "manual"


class VerificationStatus(str, enum.Enum):
    unverified = "unverified"
    verified = "verified"
    risky = "risky"
    invalid = "invalid"


class ContactStatus(str, enum.Enum):
    new = "new"
    queued = "queued"
    sent = "sent"
    opened = "opened"
    replied = "replied"
    bounced = "bounced"
    opted_out = "opted_out"
    suppressed = "suppressed"


class WorkMode(str, enum.Enum):
    onsite = "onsite"
    remote = "remote"
    hybrid = "hybrid"
    unspecified = "unspecified"


class JobOpeningStatus(str, enum.Enum):
    open = "open"
    applied = "applied"
    closed = "closed"
    irrelevant = "irrelevant"


class CampaignMode(str, enum.Enum):
    review_required = "review_required"
    auto = "auto"


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    completed = "completed"


class SendingAccountProvider(str, enum.Enum):
    gmail_oauth = "gmail_oauth"
    smtp = "smtp"
    api_resend = "api_resend"
    api_sendgrid = "api_sendgrid"


class CampaignContactStatus(str, enum.Enum):
    pending = "pending"
    queued = "queued"
    sent = "sent"
    replied = "replied"
    bounced = "bounced"
    opted_out = "opted_out"
    suppressed = "suppressed"
    completed = "completed"
    skipped = "skipped"


class BounceType(str, enum.Enum):
    none = "none"
    soft = "soft"
    hard = "hard"


class SuppressionReason(str, enum.Enum):
    opt_out = "opt_out"
    hard_bounce = "hard_bounce"
    manual_block = "manual_block"
    soft_bounce_exhausted = "soft_bounce_exhausted"


class SuppressionSource(str, enum.Enum):
    system = "system"
    user = "user"
