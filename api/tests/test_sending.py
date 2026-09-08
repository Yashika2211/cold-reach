import pytest
from sqlalchemy import select

from app.models import EmailMessage, EventLog
from app.providers.email.base import SendEmailResult
from app.services.sending import SuppressedRecipientError, send_test_email


class FakeProvider:
    """Records every send() call so tests can assert on exactly what was sent."""

    def __init__(self):
        self.send_calls = []

    async def send(self, request):
        self.send_calls.append(request)
        return SendEmailResult(provider_message_id="fake-message-id-123", thread_id="fake-thread-1")


@pytest.mark.asyncio
async def test_send_test_email_creates_message_and_event_log(
    db_session, smtp_sending_account, monkeypatch
):
    fake_provider = FakeProvider()
    monkeypatch.setattr(
        "app.services.sending.build_provider", lambda account, db=None: fake_provider
    )

    message = await send_test_email(
        db_session, smtp_sending_account, "recipient@example.com", "Test subject", "Test body"
    )

    assert len(fake_provider.send_calls) == 1
    assert message.to_email == "recipient@example.com"
    assert message.subject == "Test subject"
    assert message.body == "Test body"
    assert message.provider_message_id == "fake-message-id-123"
    assert message.thread_id == "fake-thread-1"
    assert message.sending_account_id == smtp_sending_account.id
    assert message.campaign_contact_id is None
    assert message.sent_at is not None

    stored = (
        await db_session.execute(select(EmailMessage).where(EmailMessage.id == message.id))
    ).scalar_one()
    assert stored.to_email == "recipient@example.com"

    events = (
        await db_session.execute(
            select(EventLog).where(EventLog.entity_id == message.id, EventLog.entity_type == "email_message")
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].event_type == "manual_test_send"


@pytest.mark.asyncio
async def test_send_never_reaches_provider_for_suppressed_address(
    db_session, smtp_sending_account, monkeypatch
):
    """The suppression check must sit strictly before every send — this proves the
    provider's send() is never even invoked for a suppressed recipient."""
    from app.models.enums import SuppressionReason, SuppressionSource
    from app.services.suppression import add_suppression

    await add_suppression(
        db_session, "blocked@example.com", SuppressionReason.manual_block, SuppressionSource.user
    )
    await db_session.commit()

    fake_provider = FakeProvider()
    monkeypatch.setattr(
        "app.services.sending.build_provider", lambda account, db=None: fake_provider
    )

    with pytest.raises(SuppressedRecipientError):
        await send_test_email(
            db_session, smtp_sending_account, "blocked@example.com", "Subject", "Body"
        )

    assert fake_provider.send_calls == []

    count = (
        await db_session.execute(select(EmailMessage).where(EmailMessage.to_email == "blocked@example.com"))
    ).scalars().all()
    assert count == []


@pytest.mark.asyncio
async def test_suppression_check_is_case_and_whitespace_insensitive(
    db_session, smtp_sending_account, monkeypatch
):
    from app.models.enums import SuppressionReason, SuppressionSource
    from app.services.suppression import add_suppression

    await add_suppression(
        db_session, "Case.Test@Example.com", SuppressionReason.manual_block, SuppressionSource.user
    )
    await db_session.commit()

    fake_provider = FakeProvider()
    monkeypatch.setattr(
        "app.services.sending.build_provider", lambda account, db=None: fake_provider
    )

    with pytest.raises(SuppressedRecipientError):
        await send_test_email(
            db_session, smtp_sending_account, "  case.test@example.com  ", "Subject", "Body"
        )

    assert fake_provider.send_calls == []


@pytest.mark.asyncio
async def test_from_address_and_reply_to_always_match_account_identity(
    db_session, smtp_sending_account, monkeypatch
):
    """Truthful identity (brief §2.8): from/reply-to must always be the account's own
    address, never spoofable via the send request."""
    fake_provider = FakeProvider()
    monkeypatch.setattr(
        "app.services.sending.build_provider", lambda account, db=None: fake_provider
    )

    await send_test_email(
        db_session, smtp_sending_account, "recipient@example.com", "Subject", "Body"
    )

    sent_request = fake_provider.send_calls[0]
    assert sent_request.from_email == smtp_sending_account.from_address
    assert sent_request.from_name == smtp_sending_account.display_name
    assert sent_request.reply_to == smtp_sending_account.from_address


@pytest.mark.asyncio
async def test_resume_pdf_is_attached_when_provided(db_session, smtp_sending_account, monkeypatch, tmp_path):
    from app.models import ResumeVariant

    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake resume content")

    resume = ResumeVariant(name="Backend/Data", pdf_file_path=str(pdf_path))
    db_session.add(resume)
    await db_session.flush()

    fake_provider = FakeProvider()
    monkeypatch.setattr(
        "app.services.sending.build_provider", lambda account, db=None: fake_provider
    )

    await send_test_email(
        db_session,
        smtp_sending_account,
        "recipient@example.com",
        "Subject",
        "Body",
        resume_variant=resume,
    )

    sent_request = fake_provider.send_calls[0]
    assert len(sent_request.attachments) == 1
    assert sent_request.attachments[0].filename == "Backend/Data.pdf"
    assert sent_request.attachments[0].content == b"%PDF-1.4 fake resume content"


@pytest.mark.asyncio
async def test_no_attachment_when_resume_variant_has_no_pdf(
    db_session, smtp_sending_account, monkeypatch
):
    from app.models import ResumeVariant

    resume = ResumeVariant(name="No PDF Yet")
    db_session.add(resume)
    await db_session.flush()

    fake_provider = FakeProvider()
    monkeypatch.setattr(
        "app.services.sending.build_provider", lambda account, db=None: fake_provider
    )

    await send_test_email(
        db_session,
        smtp_sending_account,
        "recipient@example.com",
        "Subject",
        "Body",
        resume_variant=resume,
    )

    assert fake_provider.send_calls[0].attachments == []
