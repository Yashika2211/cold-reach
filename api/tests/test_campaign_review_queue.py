import pytest

from app.models import Company, Contact, EmailTemplate, ResumeVariant
from app.models.enums import ContactSource
from app.schemas.generation import GeneratedEmail

GOOD_BODY = (
    "Hi {name}, saw Acme just raised a Series A and is doubling the backend team — "
    "that kind of scale-up is exactly the environment I want to build in. I've spent the "
    "last year shipping full-stack products end to end, most recently a real-time "
    "collaborative editor that handled 500 concurrent users on a self-hosted WebSocket "
    "server. I'm a final-year CS student graduating in 2027, and I'd love to trade notes "
    "on how you're approaching the scaling work — even fifteen minutes would help me "
    "understand if there's a fit here. Would it make sense to talk sometime next week? "
    "Happy to work around your schedule either way. Thanks for considering it, and "
    "congrats again on the raise — that's a big milestone for the team."
)


class FakeLLMProvider:
    def __init__(self, subject="acme + engineering", needs_more_context=False):
        self.subject = subject
        self.needs_more_context = needs_more_context
        self.calls = 0

    async def generate_structured(self, system_prompt, user_prompt, response_model):
        self.calls += 1
        name = "there"
        for line in user_prompt.split("\n"):
            if line.startswith("RECIPIENT:"):
                name = line.split(":", 1)[1].strip().split(",")[0]
        return GeneratedEmail(
            subject=self.subject,
            body=GOOD_BODY.format(name=name),
            personalization_rationale="Referenced the Series A round.",
            needs_more_context=self.needs_more_context,
        )


@pytest.fixture(autouse=True)
def no_celery_dispatch(monkeypatch):
    monkeypatch.setattr(
        "app.workers.tasks.generate_campaign_contact_draft.delay", lambda *a, **k: None
    )


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    provider = FakeLLMProvider()
    monkeypatch.setattr("app.services.email_generation.get_llm_provider", lambda: provider)
    return provider


@pytest.fixture
async def campaign_with_contacts(db_session, smtp_sending_account):
    company = Company(name="Acme Corp", research_summary="Acme just raised a Series A.")
    db_session.add(company)
    await db_session.flush()

    resume = ResumeVariant(name="SDE", positioning_summary="Ships full-stack products.")
    template = EmailTemplate(
        name="Cold outreach", subject_skeleton="{company}", body_skeleton="Hi {name}"
    )
    db_session.add_all([resume, template])
    await db_session.flush()

    contacts = []
    for i in range(10):
        c = Contact(
            first_name=f"Person{i}",
            last_name="Test",
            email=f"person{i}@example.com",
            normalized_email=f"person{i}@example.com",
            company_id=company.id,
            source=ContactSource.manual,
        )
        db_session.add(c)
        contacts.append(c)
    await db_session.flush()

    from app.models import Campaign

    campaign = Campaign(
        name="Test campaign",
        resume_variant_id=resume.id,
        email_template_id=template.id,
        sending_account_id=smtp_sending_account.id,
    )
    db_session.add(campaign)
    await db_session.flush()

    for c in contacts:
        from app.models import CampaignContact

        db_session.add(CampaignContact(campaign_id=campaign.id, contact_id=c.id))
    await db_session.flush()

    return {"campaign_id": str(campaign.id), "contacts": contacts}


@pytest.mark.asyncio
async def test_review_queue_generates_on_demand_and_approve_advances(
    auth_client, campaign_with_contacts
):
    campaign_id = campaign_with_contacts["campaign_id"]

    next_resp = await auth_client.get(f"/campaigns/{campaign_id}/review-queue/next")
    body = next_resp.json()
    assert body["remaining"] == 10
    assert body["campaign_contact"] is not None
    assert body["campaign_contact"]["current_draft"] is not None
    assert body["campaign_contact"]["current_draft"]["quality_gate"]["passed"] is True

    cc_id = body["campaign_contact"]["id"]
    approve_resp = await auth_client.post(f"/campaign-contacts/{cc_id}/approve")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "queued"

    next_resp_2 = await auth_client.get(f"/campaigns/{campaign_id}/review-queue/next")
    assert next_resp_2.json()["remaining"] == 9
    assert next_resp_2.json()["campaign_contact"]["id"] != cc_id


@pytest.mark.asyncio
async def test_approve_all_ten_contacts(auth_client, campaign_with_contacts):
    """Mirrors the Phase 5 checkpoint: build a 10-contact campaign and approve all ten."""
    campaign_id = campaign_with_contacts["campaign_id"]

    approved_ids = []
    for _ in range(10):
        next_resp = await auth_client.get(f"/campaigns/{campaign_id}/review-queue/next")
        cc = next_resp.json()["campaign_contact"]
        assert cc is not None
        approve_resp = await auth_client.post(f"/campaign-contacts/{cc['id']}/approve")
        assert approve_resp.status_code == 200
        approved_ids.append(cc["id"])

    assert len(set(approved_ids)) == 10

    final_resp = await auth_client.get(f"/campaigns/{campaign_id}/review-queue/next")
    assert final_resp.json() == {"campaign_contact": None, "remaining": 0}

    funnel = (await auth_client.get(f"/campaigns/{campaign_id}/funnel")).json()
    assert funnel["by_status"]["queued"] == 10


@pytest.mark.asyncio
async def test_approve_blocks_on_failing_quality_gate(auth_client, campaign_with_contacts, fake_llm):
    fake_llm.needs_more_context = True
    campaign_id = campaign_with_contacts["campaign_id"]

    next_resp = await auth_client.get(f"/campaigns/{campaign_id}/review-queue/next")
    cc = next_resp.json()["campaign_contact"]
    assert cc["current_draft"]["quality_gate"]["passed"] is False

    approve_resp = await auth_client.post(f"/campaign-contacts/{cc['id']}/approve")
    assert approve_resp.status_code == 422


@pytest.mark.asyncio
async def test_regenerate_appends_new_draft_with_steering_note(auth_client, campaign_with_contacts, fake_llm):
    campaign_id = campaign_with_contacts["campaign_id"]
    next_resp = await auth_client.get(f"/campaigns/{campaign_id}/review-queue/next")
    cc = next_resp.json()["campaign_contact"]

    regen_resp = await auth_client.post(
        f"/campaign-contacts/{cc['id']}/regenerate", json={"steering_note": "mention the hackathon wins"}
    )
    assert regen_resp.status_code == 200
    assert fake_llm.calls == 2  # once from review-queue/next, once from regenerate
    assert regen_resp.json()["current_draft"]["source"] == "regenerated"
    assert regen_resp.json()["current_draft"]["steering_note"] == "mention the hackathon wins"


@pytest.mark.asyncio
async def test_hand_edit_is_preserved_and_can_be_approved(auth_client, campaign_with_contacts):
    campaign_id = campaign_with_contacts["campaign_id"]
    next_resp = await auth_client.get(f"/campaigns/{campaign_id}/review-queue/next")
    cc = next_resp.json()["campaign_contact"]

    edited_body = (
        f"Hi {cc['contact_name']}, this is a personal note I wrote myself instead of using the AI draft, "
        "since I'm explicitly testing that a hand edit sticks around and can be approved "
        "afterward without being silently regenerated or overwritten by anything else in "
        "the pipeline. The quality gate still checks length even on a hand edit, which is "
        "correct — the same bar applies to every email regardless of who wrote it, so this "
        "paragraph needs to run long enough to land inside the required 120 to 160 word "
        "window for an initial outreach email, same as any AI-generated one would need to. "
        "Would it make sense to talk sometime next week? Thanks for reading this far, I "
        "appreciate it, and I hope the rest of your day goes smoothly from here on out."
    )
    edit_resp = await auth_client.patch(
        f"/campaign-contacts/{cc['id']}/edit",
        json={"subject": "a hand-edited subject line", "body": edited_body},
    )
    assert edit_resp.status_code == 200
    draft = edit_resp.json()["current_draft"]
    assert draft["source"] == "hand_edited"
    # The server always appends a fresh unsubscribe footer server-side — the operator's
    # hand-edited text is never trusted to carry a correct one itself.
    assert draft["body"].startswith(edited_body)
    assert "/unsubscribe/" in draft["body"]
    assert draft["quality_gate"]["passed"] is True, draft["quality_gate"]["failures"]

    approve_resp = await auth_client.post(f"/campaign-contacts/{cc['id']}/approve")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["current_draft"]["body"] == draft["body"]


@pytest.mark.asyncio
async def test_skip_and_suppress(auth_client, campaign_with_contacts):
    campaign_id = campaign_with_contacts["campaign_id"]

    next_resp = await auth_client.get(f"/campaigns/{campaign_id}/review-queue/next")
    cc1 = next_resp.json()["campaign_contact"]
    skip_resp = await auth_client.post(f"/campaign-contacts/{cc1['id']}/skip")
    assert skip_resp.json()["status"] == "skipped"

    next_resp_2 = await auth_client.get(f"/campaigns/{campaign_id}/review-queue/next")
    cc2 = next_resp_2.json()["campaign_contact"]
    assert cc2["id"] != cc1["id"]

    suppress_resp = await auth_client.post(f"/campaign-contacts/{cc2['id']}/suppress")
    assert suppress_resp.json()["status"] == "suppressed"

    suppression_list = await auth_client.get("/suppression")
    emails = [e["email"] for e in suppression_list.json()["items"]]
    assert cc2["contact_email"] in emails

    funnel = (await auth_client.get(f"/campaigns/{campaign_id}/funnel")).json()
    assert funnel["by_status"]["skipped"] == 1
    assert funnel["by_status"]["suppressed"] == 1
    assert funnel["by_status"]["pending"] == 8
