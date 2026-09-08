import uuid

import pytest
from sqlalchemy import select

from app.models import Contact, SuppressionEntry
from app.models.enums import ContactSource
from app.services.unsubscribe import build_unsubscribe_url, generate_unsubscribe_token


@pytest.mark.asyncio
async def test_unsubscribe_link_suppresses_the_contact(client, db_session):
    contact = Contact(
        first_name="Test",
        email="unsub-test@example.com",
        normalized_email="unsub-test@example.com",
        source=ContactSource.manual,
    )
    db_session.add(contact)
    await db_session.flush()
    await db_session.commit()

    url = build_unsubscribe_url(contact.id)
    token = url.rsplit("/", 1)[1]

    response = await client.get(f"/unsubscribe/{token}")
    assert response.status_code == 200
    assert "unsubscribed" in response.text.lower()

    result = await db_session.execute(
        select(SuppressionEntry).where(SuppressionEntry.normalized_email == "unsub-test@example.com")
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_unsubscribe_with_garbage_token_is_generic_400(client):
    response = await client.get("/unsubscribe/not-a-real-token")
    assert response.status_code == 400
    assert "invalid" in response.text.lower()


@pytest.mark.asyncio
async def test_unsubscribe_does_not_require_auth(client):
    # sanity check: this must be the one route reachable with no session at all
    token = generate_unsubscribe_token(uuid.uuid4())
    response = await client.get(f"/unsubscribe/{token}")
    assert response.status_code != 401
