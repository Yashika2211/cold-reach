import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models import Company, Contact, EmailTemplate, JobOpening, ResumeVariant
from app.providers.llm.base import LLMProvider
from app.providers.llm.groq_provider import GroqProvider
from app.schemas.generation import GeneratedEmail, GenerationResult
from app.services.quality_gate import run_quality_gate
from app.services.unsubscribe import build_unsubscribe_url

SYSTEM_PROMPT = """You write cold outreach emails for a final-year engineering student \
applying to software/data/product roles. You will be given real, specific facts about a \
company, a contact, and the sender. Follow these rules exactly:

1. LENGTH: initial emails (step 0) must be 120-160 words. Follow-ups (step 1+) must be \
under 60 words.
2. SUBJECT: lowercase-ish and specific, under 60 characters. Never use "Quick question", \
emoji, a fake "Re:"/"Fwd:" prefix, ALL CAPS, or an exclamation mark.
3. OPENING HOOK: open with something concretely true about THIS company or role, drawn \
only from the context you were given. THE SINGLE MOST IMPORTANT RULE: never fabricate a \
fact about the company, a mutual connection, or a product. If the context has nothing \
specific enough to personalize on honestly, set needs_more_context=true instead of \
inventing a detail — but if you were given usable facts (company research, a role, or \
sender projects), use them and write the email; needs_more_context is for when the \
context is genuinely too thin, not a default. The same no-fabrication rule applies to the \
sender's own projects: you may restate numbers you were given (e.g. "500 concurrent \
users") but do not invent new ones (no made-up latency/RAM figures or extra claims beyond \
what SENDER HIGHLIGHT PROJECTS says).
4. ASK: end with one clear, low-friction ask ("Would it make sense to talk?"), never \
"please consider my application for the following positions" or similar corporate phrasing.
5. TONE: no superlatives about the sender, no "I am writing to express my keen interest", \
no corporate filler. Write like a specific, competent human, not a template.
6. FOLLOW-UPS (step 1+): briefly reference the original email and add one new piece of \
value (a shipped project, a relevant link) rather than just "bumping this".
7. Do not write an unsubscribe line or footer — that is appended separately.

Respond with ONLY a JSON object matching this exact shape, no other text:
{"subject": string, "body": string, "personalization_rationale": string, "needs_more_context": boolean}
"""


@dataclass
class GenerationContext:
    contact: Contact
    resume_variant: ResumeVariant
    template: EmailTemplate
    step_number: int
    company: Company | None = None
    job_opening: JobOpening | None = None
    steering_note: str | None = None


async def assemble_context(
    db: AsyncSession,
    contact_id: uuid.UUID,
    resume_variant_id: uuid.UUID,
    template_id: uuid.UUID,
    step_number: int,
    job_opening_id: uuid.UUID | None = None,
    steering_note: str | None = None,
) -> GenerationContext:
    contact_result = await db.execute(
        select(Contact).options(selectinload(Contact.company)).where(Contact.id == contact_id)
    )
    contact = contact_result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    resume_variant = await db.get(ResumeVariant, resume_variant_id)
    if resume_variant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume variant not found")

    template = await db.get(EmailTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email template not found")

    job_opening = None
    if job_opening_id is not None:
        job_opening = await db.get(JobOpening, job_opening_id)
        if job_opening is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job opening not found")

    return GenerationContext(
        contact=contact,
        resume_variant=resume_variant,
        template=template,
        step_number=step_number,
        company=contact.company,
        job_opening=job_opening,
        steering_note=steering_note,
    )


def build_user_prompt(ctx: GenerationContext) -> str:
    lines: list[str] = []

    recipient_name = " ".join(filter(None, [ctx.contact.first_name, ctx.contact.last_name])) or "there"
    lines.append(f"RECIPIENT: {recipient_name}" + (f", {ctx.contact.title}" if ctx.contact.title else ""))

    if ctx.company:
        lines.append(f"COMPANY: {ctx.company.name}")
        if ctx.company.industry:
            lines.append(f"INDUSTRY: {ctx.company.industry}")
        if ctx.company.research_summary:
            lines.append(
                "COMPANY RESEARCH (the only source of company facts you may use):\n"
                f"{ctx.company.research_summary}"
            )
        else:
            lines.append("COMPANY RESEARCH: none provided.")
    else:
        lines.append("COMPANY: unknown. COMPANY RESEARCH: none provided.")

    if ctx.job_opening:
        lines.append(f"TARGET ROLE: {ctx.job_opening.title}")
        if ctx.job_opening.raw_description:
            excerpt = ctx.job_opening.raw_description[:800]
            lines.append(f"ROLE DESCRIPTION EXCERPT:\n{excerpt}")

    positioning = ctx.resume_variant.positioning_summary or "n/a"
    lines.append(f"SENDER POSITIONING ({ctx.resume_variant.name}): {positioning}")
    if ctx.resume_variant.highlight_projects:
        lines.append("SENDER HIGHLIGHT PROJECTS: " + "; ".join(ctx.resume_variant.highlight_projects))

    lines.append(f"TEMPLATE SUBJECT SKELETON: {ctx.template.subject_skeleton}")
    lines.append(
        "TEMPLATE BODY SKELETON (a starting point, not a mail-merge string): "
        f"{ctx.template.body_skeleton}"
    )
    if ctx.template.llm_instructions:
        lines.append(f"TEMPLATE-SPECIFIC INSTRUCTIONS: {ctx.template.llm_instructions}")

    step_label = "initial email" if ctx.step_number == 0 else f"follow-up {ctx.step_number}"
    lines.append(f"STEP NUMBER: {ctx.step_number} ({step_label})")

    if ctx.steering_note:
        lines.append(f"STEERING NOTE FROM THE OPERATOR (apply this to the regeneration): {ctx.steering_note}")

    return "\n\n".join(lines)


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "groq":
        return GroqProvider(api_key=settings.groq_api_key, model=settings.groq_model)
    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


async def generate_email(ctx: GenerationContext, llm: LLMProvider | None = None) -> GenerationResult:
    llm = llm or get_llm_provider()
    user_prompt = build_user_prompt(ctx)
    generated: GeneratedEmail = await llm.generate_structured(SYSTEM_PROMPT, user_prompt, GeneratedEmail)

    unsubscribe_url = build_unsubscribe_url(ctx.contact.id)
    final_body = (
        generated.body.rstrip()
        + f"\n\n---\nDon't want future emails? Unsubscribe: {unsubscribe_url}"
    )

    quality_gate = run_quality_gate(generated, final_body, ctx.contact, ctx.step_number)

    return GenerationResult(
        subject=generated.subject,
        body=final_body,
        personalization_rationale=generated.personalization_rationale,
        needs_more_context=generated.needs_more_context,
        quality_gate=quality_gate,
    )
