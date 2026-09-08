from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailMessage, EventLog, ResumeVariant, SendingAccount
from app.providers.email.base import EmailAttachment, SendEmailRequest
from app.services.sending_accounts import build_provider
from app.services.suppression import is_suppressed


class SuppressedRecipientError(Exception):
    """Raised whenever a send is attempted against a suppressed address. Every send
    code path must go through this check — no exceptions."""


def _build_attachments(resume_variant: ResumeVariant | None) -> list[EmailAttachment]:
    if resume_variant is None or not resume_variant.pdf_file_path:
        return []
    path = Path(resume_variant.pdf_file_path)
    if not path.exists():
        return []
    return [
        EmailAttachment(
            filename=f"{resume_variant.name}.pdf",
            content=path.read_bytes(),
            mime_type="application/pdf",
        )
    ]


async def send_test_email(
    db: AsyncSession,
    account: SendingAccount,
    to_email: str,
    subject: str,
    body_text: str,
    resume_variant: ResumeVariant | None = None,
) -> EmailMessage:
    if await is_suppressed(db, to_email):
        raise SuppressedRecipientError(f"{to_email} is on the suppression list")

    provider = build_provider(account, db)
    request = SendEmailRequest(
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        # Truthful identity (§2.8): always the account's own address. Never
        # caller-suppliable, so a spoofed From/Reply-To is structurally impossible here.
        from_email=account.from_address,
        from_name=account.display_name,
        reply_to=account.from_address,
        attachments=_build_attachments(resume_variant),
    )
    result = await provider.send(request)

    email_message = EmailMessage(
        sending_account_id=account.id,
        campaign_contact_id=None,
        step_number=0,
        to_email=to_email,
        subject=subject,
        body=body_text,
        provider_message_id=result.provider_message_id,
        thread_id=result.thread_id,
        sent_at=datetime.now(UTC),
    )
    db.add(email_message)
    await db.flush()

    db.add(
        EventLog(
            entity_type="email_message",
            entity_id=email_message.id,
            event_type="manual_test_send",
            payload={
                "sending_account_id": str(account.id),
                "to_email": to_email,
                "provider_message_id": result.provider_message_id,
            },
        )
    )

    await db.commit()
    await db.refresh(email_message, attribute_names=["updated_at"])
    return email_message
