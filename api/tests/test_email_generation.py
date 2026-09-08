import uuid

import pytest

from app.models import Company, Contact, EmailTemplate, ResumeVariant
from app.models.enums import ContactSource
from app.schemas.generation import GeneratedEmail
from app.services.email_generation import assemble_context, build_user_prompt, generate_email


class FakeLLMProvider:
    def __init__(self, response: GeneratedEmail):
        self.response = response
        self.calls: list[tuple[str, str]] = []

    async def generate_structured(self, system_prompt, user_prompt, response_model):
        self.calls.append((system_prompt, user_prompt))
        return self.response


GOOD_BODY = (
    "Hi Priya, saw TechFlow just closed a Series B and is doubling the backend team — "
    "that kind of scale-up is exactly the environment I want to build in. I've spent the "
    "last year shipping a real-time data pipeline that handled 40x traffic growth without "
    "a rewrite, which sounds close to the problem you're probably fighting right now. "
    "I'm a final-year CS student graduating in 2027, and I'd love to trade notes on how "
    "you're approaching the scaling work — even fifteen minutes would help me understand "
    "if there's a fit here. Would it make sense to talk sometime next week? "
    "Happy to work around your schedule, and I can share more specifics on the pipeline "
    "project if useful. Thanks for considering it, and congrats again on the raise."
)


@pytest.fixture
async def sample_entities(db_session):
    company = Company(
        name="TechFlow",
        industry="Fintech",
        research_summary="TechFlow closed a $30M Series B in March and is doubling its backend team.",
    )
    db_session.add(company)
    await db_session.flush()

    contact = Contact(
        first_name="Priya",
        last_name="Sharma",
        email="priya@techflow.io",
        normalized_email="priya@techflow.io",
        title="Engineering Manager",
        company_id=company.id,
        source=ContactSource.manual,
    )
    db_session.add(contact)

    resume = ResumeVariant(
        name="Backend/Data",
        role_family="data-engineering",
        positioning_summary="Final-year CS student who ships production data pipelines.",
        highlight_projects=["Real-time pipeline handling 40x traffic growth"],
    )
    db_session.add(resume)

    template = EmailTemplate(
        name="Cold outreach - engineering",
        subject_skeleton="{company} + {name}",
        body_skeleton="Hi {name}, ...",
        llm_instructions="Keep it casual and specific.",
    )
    db_session.add(template)

    await db_session.flush()
    return {"company": company, "contact": contact, "resume": resume, "template": template}


@pytest.mark.asyncio
async def test_assemble_context_gathers_everything(db_session, sample_entities):
    ctx = await assemble_context(
        db_session,
        contact_id=sample_entities["contact"].id,
        resume_variant_id=sample_entities["resume"].id,
        template_id=sample_entities["template"].id,
        step_number=0,
    )
    assert ctx.contact.email == "priya@techflow.io"
    assert ctx.company.name == "TechFlow"
    assert ctx.resume_variant.name == "Backend/Data"
    assert ctx.template.name == "Cold outreach - engineering"


@pytest.mark.asyncio
async def test_assemble_context_404s_on_missing_contact(db_session, sample_entities):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await assemble_context(
            db_session,
            contact_id=uuid.uuid4(),
            resume_variant_id=sample_entities["resume"].id,
            template_id=sample_entities["template"].id,
            step_number=0,
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_user_prompt_includes_company_research_and_no_fabrication_allowed(
    db_session, sample_entities
):
    ctx = await assemble_context(
        db_session,
        contact_id=sample_entities["contact"].id,
        resume_variant_id=sample_entities["resume"].id,
        template_id=sample_entities["template"].id,
        step_number=0,
    )
    prompt = build_user_prompt(ctx)
    assert "Series B" in prompt
    assert "Priya" in prompt
    assert "Backend/Data" in prompt


@pytest.mark.asyncio
async def test_generate_email_appends_unsubscribe_and_runs_quality_gate(db_session, sample_entities):
    ctx = await assemble_context(
        db_session,
        contact_id=sample_entities["contact"].id,
        resume_variant_id=sample_entities["resume"].id,
        template_id=sample_entities["template"].id,
        step_number=0,
    )
    fake_llm = FakeLLMProvider(
        GeneratedEmail(
            subject="noticed techflow's series b",
            body=GOOD_BODY,
            personalization_rationale="Referenced the Series B round from company research.",
            needs_more_context=False,
        )
    )

    result = await generate_email(ctx, llm=fake_llm)

    assert "unsubscribe" in result.body.lower()
    assert result.quality_gate.passed is True, result.quality_gate.failures
    assert len(fake_llm.calls) == 1


@pytest.mark.asyncio
async def test_generate_email_needs_more_context_blocks_quality_gate(db_session, sample_entities):
    ctx = await assemble_context(
        db_session,
        contact_id=sample_entities["contact"].id,
        resume_variant_id=sample_entities["resume"].id,
        template_id=sample_entities["template"].id,
        step_number=0,
    )
    fake_llm = FakeLLMProvider(
        GeneratedEmail(
            subject="hello",
            body=GOOD_BODY,
            personalization_rationale="n/a",
            needs_more_context=True,
        )
    )

    result = await generate_email(ctx, llm=fake_llm)
    assert result.quality_gate.passed is False
    assert result.needs_more_context is True


@pytest.mark.asyncio
async def test_preview_endpoint_returns_generation_result(
    auth_client, db_session, sample_entities, monkeypatch
):
    fake_llm = FakeLLMProvider(
        GeneratedEmail(
            subject="noticed techflow's series b",
            body=GOOD_BODY,
            personalization_rationale="Referenced the Series B round.",
            needs_more_context=False,
        )
    )
    monkeypatch.setattr("app.services.email_generation.get_llm_provider", lambda: fake_llm)

    response = await auth_client.post(
        "/email-generation/preview",
        json={
            "contact_id": str(sample_entities["contact"].id),
            "resume_variant_id": str(sample_entities["resume"].id),
            "template_id": str(sample_entities["template"].id),
            "step_number": 0,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["quality_gate"]["passed"] is True
    assert "unsubscribe" in body["body"].lower()
