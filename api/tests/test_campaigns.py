import pytest

from app.models import Company, Contact, EmailTemplate, ResumeVariant
from app.models.enums import ContactSource


@pytest.fixture(autouse=True)
def no_celery_dispatch(monkeypatch):
    """Campaign contact creation dispatches a Celery task to pre-generate the first
    draft. Tests don't run a worker, so make .delay() a harmless no-op — the
    synchronous fallback in the review-queue endpoint is what tests actually exercise."""
    monkeypatch.setattr(
        "app.workers.tasks.generate_campaign_contact_draft.delay", lambda *a, **k: None
    )


@pytest.fixture
async def campaign_setup(db_session, smtp_sending_account):
    resume = ResumeVariant(name="SDE", positioning_summary="Ships full-stack products.")
    template = EmailTemplate(
        name="Cold outreach",
        subject_skeleton="{company}",
        body_skeleton="Hi {name}",
        llm_instructions="Be specific.",
    )
    db_session.add_all([resume, template])
    await db_session.flush()
    return {
        "resume_variant_id": str(resume.id),
        "email_template_id": str(template.id),
        "sending_account_id": str(smtp_sending_account.id),
    }


@pytest.fixture
async def sample_contacts(db_session):
    company = Company(name="Acme Corp", research_summary="Acme just raised a Series A.")
    db_session.add(company)
    await db_session.flush()

    contacts = []
    for i in range(3):
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
    return contacts


@pytest.mark.asyncio
async def test_create_and_get_campaign(auth_client, campaign_setup):
    response = await auth_client.post(
        "/campaigns",
        json={"name": "Q1 outreach", **campaign_setup},
    )
    assert response.status_code == 201, response.text
    campaign = response.json()
    assert campaign["mode"] == "review_required"
    assert campaign["daily_cap"] == 40
    assert campaign["status"] == "draft"

    get_resp = await auth_client.get(f"/campaigns/{campaign['id']}")
    assert get_resp.status_code == 200


@pytest.mark.asyncio
async def test_daily_cap_ceiling_enforced(auth_client, campaign_setup):
    response = await auth_client.post(
        "/campaigns", json={"name": "Too big", "daily_cap": 151, **campaign_setup}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_and_delete_campaign(auth_client, campaign_setup):
    create_resp = await auth_client.post("/campaigns", json={"name": "Original", **campaign_setup})
    campaign_id = create_resp.json()["id"]

    patch_resp = await auth_client.patch(f"/campaigns/{campaign_id}", json={"name": "Renamed"})
    assert patch_resp.json()["name"] == "Renamed"

    delete_resp = await auth_client.delete(f"/campaigns/{campaign_id}")
    assert delete_resp.status_code == 204

    missing_resp = await auth_client.get(f"/campaigns/{campaign_id}")
    assert missing_resp.status_code == 404


@pytest.mark.asyncio
async def test_add_contacts_dedupes_and_skips_invalid(auth_client, campaign_setup, sample_contacts):
    create_resp = await auth_client.post("/campaigns", json={"name": "Test", **campaign_setup})
    campaign_id = create_resp.json()["id"]

    contact_ids = [str(c.id) for c in sample_contacts]
    fake_id = "00000000-0000-0000-0000-000000000000"

    add_resp = await auth_client.post(
        f"/campaigns/{campaign_id}/contacts", json={"contact_ids": [*contact_ids, fake_id]}
    )
    assert add_resp.status_code == 200
    assert add_resp.json()["added"] == 3

    # Adding the same contacts again should add zero new rows.
    second_resp = await auth_client.post(
        f"/campaigns/{campaign_id}/contacts", json={"contact_ids": contact_ids}
    )
    assert second_resp.json()["added"] == 0

    list_resp = await auth_client.get(f"/campaigns/{campaign_id}/contacts")
    assert len(list_resp.json()) == 3


@pytest.mark.asyncio
async def test_funnel_counts_by_status(auth_client, campaign_setup, sample_contacts):
    create_resp = await auth_client.post("/campaigns", json={"name": "Test", **campaign_setup})
    campaign_id = create_resp.json()["id"]

    contact_ids = [str(c.id) for c in sample_contacts]
    await auth_client.post(f"/campaigns/{campaign_id}/contacts", json={"contact_ids": contact_ids})

    funnel_resp = await auth_client.get(f"/campaigns/{campaign_id}/funnel")
    body = funnel_resp.json()
    assert body["total"] == 3
    assert body["by_status"]["pending"] == 3
