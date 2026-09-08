from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CampaignContact
from app.models.enums import CampaignContactStatus
from app.providers.llm.base import LLMProvider
from app.schemas.campaign import CampaignContactRead, EmailDraft
from app.schemas.generation import GeneratedEmail
from app.services.email_generation import GenerationContext, assemble_context, generate_email
from app.services.quality_gate import run_quality_gate
from app.services.unsubscribe import append_unsubscribe_footer


class NoDraftError(Exception):
    """Raised when an action needs a current draft but none exists yet."""


class QualityGateFailedError(Exception):
    """Raised when approval is attempted on a draft that fails the quality gate."""


async def assemble_context_for_campaign_contact(
    db: AsyncSession, campaign_contact: CampaignContact
) -> GenerationContext:
    campaign = campaign_contact.campaign
    return await assemble_context(
        db,
        contact_id=campaign_contact.contact_id,
        resume_variant_id=campaign.resume_variant_id,
        template_id=campaign.email_template_id,
        step_number=campaign_contact.current_step,
        job_opening_id=campaign.job_opening_id,
    )


def to_campaign_contact_read(cc: CampaignContact) -> CampaignContactRead:
    """Shared by every route that returns a CampaignContact so the shape never drifts.
    Requires cc.contact to already be eager-loaded by the caller."""
    draft = get_current_draft(cc)
    return CampaignContactRead(
        id=cc.id,
        campaign_id=cc.campaign_id,
        contact_id=cc.contact_id,
        contact_email=cc.contact.email,
        contact_name=(
            " ".join(filter(None, [cc.contact.first_name, cc.contact.last_name])) or cc.contact.email
        ),
        current_step=cc.current_step,
        status=cc.status,
        current_draft=EmailDraft(**draft) if draft else None,
        created_at=cc.created_at,
        updated_at=cc.updated_at,
    )


def get_current_draft(campaign_contact: CampaignContact) -> dict | None:
    """The latest history entry for the contact's current step, or None if it
    hasn't been generated yet."""
    entries = [
        e for e in campaign_contact.generated_email_history
        if e["step_number"] == campaign_contact.current_step
    ]
    return entries[-1] if entries else None


async def generate_draft(
    db: AsyncSession,
    campaign_contact: CampaignContact,
    llm: LLMProvider | None = None,
    steering_note: str | None = None,
    source: str = "generated",
) -> dict:
    ctx = await assemble_context_for_campaign_contact(db, campaign_contact)
    ctx.steering_note = steering_note

    result = await generate_email(ctx, llm=llm)

    entry = {
        "step_number": campaign_contact.current_step,
        "subject": result.subject,
        "body": result.body,
        "personalization_rationale": result.personalization_rationale,
        "needs_more_context": result.needs_more_context,
        "quality_gate": result.quality_gate.model_dump(),
        "source": source,
        "steering_note": steering_note,
        "created_at": datetime.now(UTC).isoformat(),
    }

    campaign_contact.generated_email_history = [*campaign_contact.generated_email_history, entry]
    return entry


async def hand_edit_draft(campaign_contact: CampaignContact, subject: str, body: str) -> dict:
    final_body = append_unsubscribe_footer(body, campaign_contact.contact_id)

    generated = GeneratedEmail(
        subject=subject, body=final_body, personalization_rationale="Hand-edited by operator."
    )
    quality_gate = run_quality_gate(
        generated, final_body, campaign_contact.contact, campaign_contact.current_step
    )

    entry = {
        "step_number": campaign_contact.current_step,
        "subject": subject,
        "body": final_body,
        "personalization_rationale": "Hand-edited by operator.",
        "needs_more_context": False,
        "quality_gate": quality_gate.model_dump(),
        "source": "hand_edited",
        "steering_note": None,
        "created_at": datetime.now(UTC).isoformat(),
    }

    campaign_contact.generated_email_history = [*campaign_contact.generated_email_history, entry]
    return entry


def approve(campaign_contact: CampaignContact) -> None:
    draft = get_current_draft(campaign_contact)
    if draft is None:
        raise NoDraftError("No draft has been generated for this contact yet")
    if not draft["quality_gate"]["passed"]:
        raise QualityGateFailedError(
            f"Draft fails the quality gate: {', '.join(draft['quality_gate']['failures'])}"
        )
    campaign_contact.status = CampaignContactStatus.queued


def skip(campaign_contact: CampaignContact) -> None:
    campaign_contact.status = CampaignContactStatus.skipped
