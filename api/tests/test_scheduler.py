import uuid
from datetime import UTC, datetime, timedelta
from datetime import time as dt_time

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models import (
    Campaign,
    CampaignContact,
    Company,
    Contact,
    EmailMessage,
    EmailTemplate,
    EventLog,
    ResumeVariant,
)
from app.models.enums import (
    CampaignContactStatus,
    CampaignStatus,
    ContactSource,
    SuppressionReason,
    SuppressionSource,
)
from app.providers.email.base import SendEmailResult
from app.services.scheduler import (
    acquire_send_lock,
    get_remaining_quota,
    is_within_send_window,
    random_jitter_seconds,
    reserve_quota_slot,
)
from app.services.suppression import add_suppression
from tests.conftest import TEST_REDIS_URL

# A fixed, unambiguous instant: Tuesday 2024-01-02, 10:00 UTC.
TUESDAY_10AM_UTC = datetime(2024, 1, 2, 10, 0, tzinfo=UTC)
MONDAY_10AM_UTC = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)


def _make_campaign(**overrides) -> Campaign:
    """An in-memory (unpersisted) Campaign for pure-logic tests that never touch the DB."""
    defaults = dict(
        id=uuid.uuid4(),
        name="Window test campaign",
        resume_variant_id=uuid.uuid4(),
        email_template_id=uuid.uuid4(),
        sending_account_id=uuid.uuid4(),
        daily_cap=40,
        send_window_start_local=dt_time(9, 0),
        send_window_end_local=dt_time(11, 30),
        send_window_days=[1, 2, 3],  # Tue, Wed, Thu
        timezone="UTC",
        follow_up_schedule_days=[4, 9],
    )
    defaults.update(overrides)
    return Campaign(**defaults)


# ---------------------------------------------------------------------------
# Pure logic: jitter and send-window
# ---------------------------------------------------------------------------


def test_random_jitter_seconds_stays_within_45_to_180_range():
    values = [random_jitter_seconds() for _ in range(500)]
    assert all(45 <= v <= 180 for v in values)
    # Not a constant — the whole point is randomization.
    assert len(set(values)) > 1


def test_is_within_send_window_true_inside_window_and_correct_weekday():
    campaign = _make_campaign()
    assert is_within_send_window(campaign, now=TUESDAY_10AM_UTC) is True


def test_is_within_send_window_false_before_window_start():
    campaign = _make_campaign()
    before_open = TUESDAY_10AM_UTC.replace(hour=8, minute=0)
    assert is_within_send_window(campaign, now=before_open) is False


def test_is_within_send_window_false_after_window_end():
    campaign = _make_campaign()
    after_close = TUESDAY_10AM_UTC.replace(hour=12, minute=0)
    assert is_within_send_window(campaign, now=after_close) is False


def test_is_within_send_window_false_on_wrong_weekday():
    campaign = _make_campaign()
    assert is_within_send_window(campaign, now=MONDAY_10AM_UTC) is False


def test_is_within_send_window_respects_campaign_timezone():
    """10:00 UTC is 15:30 IST — well outside a 09:00-11:30 Asia/Kolkata window,
    even though the same instant passes for a UTC-windowed campaign."""
    campaign = _make_campaign(timezone="Asia/Kolkata")
    assert is_within_send_window(campaign, now=TUESDAY_10AM_UTC) is False


# ---------------------------------------------------------------------------
# Quota (Redis-backed) — no DB needed, just redis_client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_remaining_quota_uses_the_lower_of_campaign_and_account_caps(
    redis_client, smtp_sending_account
):
    smtp_sending_account.daily_cap = 100
    campaign = _make_campaign(daily_cap=3)

    remaining = await get_remaining_quota(redis_client, campaign, smtp_sending_account)
    assert remaining == 3


@pytest.mark.asyncio
async def test_reserve_quota_slot_decrements_remaining(redis_client, smtp_sending_account):
    smtp_sending_account.daily_cap = 40
    campaign = _make_campaign(daily_cap=5)

    assert await get_remaining_quota(redis_client, campaign, smtp_sending_account) == 5
    await reserve_quota_slot(redis_client, campaign, smtp_sending_account)
    assert await get_remaining_quota(redis_client, campaign, smtp_sending_account) == 4


@pytest.mark.asyncio
async def test_quota_hits_zero_and_never_goes_negative(redis_client, smtp_sending_account):
    smtp_sending_account.daily_cap = 40
    campaign = _make_campaign(daily_cap=2)

    for _ in range(2):
        await reserve_quota_slot(redis_client, campaign, smtp_sending_account)
    assert await get_remaining_quota(redis_client, campaign, smtp_sending_account) == 0

    # A further reservation attempt (e.g. a racing tick) must not push it negative.
    await reserve_quota_slot(redis_client, campaign, smtp_sending_account)
    assert await get_remaining_quota(redis_client, campaign, smtp_sending_account) == 0


@pytest.mark.asyncio
async def test_quota_campaign_counters_are_isolated_but_account_counter_is_shared(
    redis_client, smtp_sending_account
):
    smtp_sending_account.daily_cap = 100
    campaign_a = _make_campaign(daily_cap=10)
    campaign_b = _make_campaign(daily_cap=10)

    await reserve_quota_slot(redis_client, campaign_a, smtp_sending_account)

    # campaign_a's own per-campaign counter went down...
    assert await get_remaining_quota(redis_client, campaign_a, smtp_sending_account) == 9
    # ...but campaign_b's per-campaign counter is untouched, and the account cap
    # (100) is nowhere near exhausted, so campaign_b's remaining is governed purely
    # by its own cap.
    assert await get_remaining_quota(redis_client, campaign_b, smtp_sending_account) == 10

    # Now exhaust the shared account-level cap and confirm it gates BOTH campaigns.
    smtp_sending_account.daily_cap = 1
    assert await get_remaining_quota(redis_client, campaign_a, smtp_sending_account) == 0
    assert await get_remaining_quota(redis_client, campaign_b, smtp_sending_account) == 0


# ---------------------------------------------------------------------------
# Idempotency lock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acquire_send_lock_only_succeeds_once(redis_client):
    contact_id = uuid.uuid4()
    assert await acquire_send_lock(redis_client, contact_id) is True
    assert await acquire_send_lock(redis_client, contact_id) is False


@pytest.mark.asyncio
async def test_acquire_send_lock_is_independent_per_contact(redis_client):
    assert await acquire_send_lock(redis_client, uuid.uuid4()) is True
    assert await acquire_send_lock(redis_client, uuid.uuid4()) is True


# ---------------------------------------------------------------------------
# Task-body integration tests: exercise the real Celery task coroutines against
# the test database, with a fake email provider standing in for real send.
# ---------------------------------------------------------------------------


class FakeProvider:
    def __init__(self):
        self.send_calls = []

    async def send(self, request):
        self.send_calls.append(request)
        return SendEmailResult(provider_message_id="fake-msg-id", thread_id="fake-thread-id")


@pytest_asyncio.fixture
async def task_session_maker(db_connection, monkeypatch):
    """The Celery task bodies build their own session via AsyncSessionLocal rather
    than receiving one through FastAPI's DI. Binding a second sessionmaker to the
    exact same connection/transaction as db_session means both see each other's
    writes and everything still rolls back together at teardown."""
    session_maker = async_sessionmaker(bind=db_connection, expire_on_commit=False)
    monkeypatch.setattr("app.workers.tasks.AsyncSessionLocal", session_maker)
    return session_maker


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.workers.tasks.build_provider", lambda account, db=None: provider)
    return provider


@pytest.fixture(autouse=True)
def no_apply_async(monkeypatch):
    """scheduler_tick fires send_queued_email.apply_async(countdown=...) — replace it
    with a plain recorder so tests never touch a real Celery broker."""
    calls = []
    monkeypatch.setattr(
        "app.workers.tasks.send_queued_email.apply_async",
        lambda args, countdown=None: calls.append({"args": args, "countdown": countdown}),
    )
    return calls


def _passing_draft(step_number: int = 0) -> dict:
    return {
        "step_number": step_number,
        "subject": "Loved what Acme is building",
        "body": (
            "Hi there, this is a fully-formed test draft body that is long enough to "
            "read as a real outreach email for the purposes of this scheduler test, "
            "well past the minimum word count the quality gate enforces for an "
            "initial outreach message so it reliably reads as passing in every check "
            "that only inspects the stored quality_gate.passed flag rather than "
            "re-running the gate itself. Unsubscribe: https://example.com/unsubscribe/tok123"
        ),
        "personalization_rationale": "Test fixture draft.",
        "needs_more_context": False,
        "quality_gate": {"passed": True, "failures": []},
        "source": "generated",
        "steering_note": None,
        "created_at": datetime.now(UTC).isoformat(),
    }


@pytest_asyncio.fixture
async def scheduling_setup(db_session, task_session_maker, redis_client, monkeypatch, smtp_sending_account):
    """A campaign with a send window open at all times (avoids wall-clock flakiness),
    one contact already approved+queued with a passing draft and a due next_action_at."""
    # The task bodies call new_redis_client() directly (a fresh client per call —
    # see app/core/redis.py) rather than going through FastAPI DI, so
    # app.dependency_overrides[get_redis] (used by API tests) never reaches them.
    # Point that factory at the same isolated test Redis DB as redis_client; each
    # call still gets its own connection (mirroring production), but all of them
    # talk to the same server-side db 15, so state set up via redis_client directly
    # is visible to the task and vice versa.
    monkeypatch.setattr(
        "app.workers.tasks.new_redis_client",
        lambda: Redis.from_url(TEST_REDIS_URL, decode_responses=True),
    )
    company = Company(name="Acme Corp")
    db_session.add(company)
    await db_session.flush()

    resume = ResumeVariant(name="SDE")
    template = EmailTemplate(name="Cold outreach", subject_skeleton="{company}", body_skeleton="Hi {name}")
    db_session.add_all([resume, template])
    await db_session.flush()

    contact = Contact(
        first_name="Jamie",
        last_name="Recruiter",
        email="jamie@example.com",
        normalized_email="jamie@example.com",
        company_id=company.id,
        source=ContactSource.manual,
    )
    db_session.add(contact)
    await db_session.flush()

    campaign = Campaign(
        name="Always-open scheduling test campaign",
        resume_variant_id=resume.id,
        email_template_id=template.id,
        sending_account_id=smtp_sending_account.id,
        status=CampaignStatus.active,
        daily_cap=40,
        send_window_start_local=dt_time(0, 0),
        send_window_end_local=dt_time(23, 59),
        send_window_days=[0, 1, 2, 3, 4, 5, 6],
        timezone="UTC",
        follow_up_schedule_days=[4, 9],
    )
    db_session.add(campaign)
    await db_session.flush()

    cc = CampaignContact(
        campaign_id=campaign.id,
        contact_id=contact.id,
        status=CampaignContactStatus.queued,
        next_action_at=datetime.now(UTC) - timedelta(minutes=1),
        current_step=0,
        generated_email_history=[_passing_draft(step_number=0)],
    )
    db_session.add(cc)
    await db_session.flush()
    await db_session.commit()

    return {
        "campaign": campaign,
        "campaign_contact": cc,
        "contact": contact,
        "sending_account": smtp_sending_account,
    }


@pytest.mark.asyncio
async def test_scheduler_tick_schedules_the_eligible_due_contact(
    db_session, scheduling_setup, no_apply_async
):
    from app.workers.tasks import _scheduler_tick_async

    await _scheduler_tick_async()

    assert len(no_apply_async) == 1
    assert no_apply_async[0]["args"] == [str(scheduling_setup["campaign_contact"].id)]
    assert 45 <= no_apply_async[0]["countdown"] <= 180


@pytest.mark.asyncio
async def test_scheduler_tick_does_nothing_while_globally_paused(
    db_session, redis_client, scheduling_setup, no_apply_async
):
    from app.services.scheduler import set_global_pause
    from app.workers.tasks import _scheduler_tick_async

    await set_global_pause(redis_client, True)
    await _scheduler_tick_async()

    assert no_apply_async == []


@pytest.mark.asyncio
async def test_scheduler_tick_skips_campaign_outside_its_send_window(
    db_session, scheduling_setup, no_apply_async
):
    from app.workers.tasks import _scheduler_tick_async

    campaign = scheduling_setup["campaign"]
    campaign.send_window_days = []  # never in window on any day
    await db_session.commit()

    await _scheduler_tick_async()

    assert no_apply_async == []


@pytest.mark.asyncio
async def test_scheduler_tick_stops_at_the_daily_cap(
    db_session, redis_client, scheduling_setup, no_apply_async
):
    from app.workers.tasks import _scheduler_tick_async

    campaign = scheduling_setup["campaign"]
    campaign.daily_cap = 0
    await db_session.commit()

    await _scheduler_tick_async()

    assert no_apply_async == []


@pytest.mark.asyncio
async def test_scheduler_tick_marks_newly_suppressed_contact_and_does_not_schedule(
    db_session, scheduling_setup, no_apply_async
):
    from app.workers.tasks import _scheduler_tick_async

    await add_suppression(
        db_session, "jamie@example.com", SuppressionReason.manual_block, SuppressionSource.user
    )
    await db_session.commit()

    await _scheduler_tick_async()

    assert no_apply_async == []
    await db_session.refresh(scheduling_setup["campaign_contact"])
    assert scheduling_setup["campaign_contact"].status == CampaignContactStatus.suppressed


@pytest.mark.asyncio
async def test_scheduler_tick_ignores_contact_not_yet_due(db_session, scheduling_setup, no_apply_async):
    from app.workers.tasks import _scheduler_tick_async

    cc = scheduling_setup["campaign_contact"]
    cc.next_action_at = datetime.now(UTC) + timedelta(hours=1)
    await db_session.commit()

    await _scheduler_tick_async()

    assert no_apply_async == []


# ---------------------------------------------------------------------------
# send_queued_email task body
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_queued_email_sends_persists_and_advances_to_first_follow_up(
    db_session, scheduling_setup, fake_provider
):
    from app.workers.tasks import _send_queued_email_async

    cc = scheduling_setup["campaign_contact"]
    campaign = scheduling_setup["campaign"]

    await _send_queued_email_async(cc.id)

    assert len(fake_provider.send_calls) == 1
    sent_request = fake_provider.send_calls[0]
    assert sent_request.to_email == "jamie@example.com"
    assert sent_request.from_email == scheduling_setup["sending_account"].from_address

    message = (
        await db_session.execute(select(EmailMessage).where(EmailMessage.campaign_contact_id == cc.id))
    ).scalar_one()
    assert message.provider_message_id == "fake-msg-id"
    assert message.step_number == 0

    event = (
        await db_session.execute(
            select(EventLog).where(EventLog.entity_id == cc.id, EventLog.event_type == "sent")
        )
    ).scalar_one_or_none()
    assert event is not None

    await db_session.refresh(cc)
    await db_session.refresh(campaign)
    assert campaign.sent_count == 1
    # follow_up_schedule_days=[4, 9] — after step 0, the next follow-up is 4 days out.
    assert cc.current_step == 1
    assert cc.status == CampaignContactStatus.pending
    expected_next = message.sent_at + timedelta(days=4)
    assert abs((cc.next_action_at - expected_next).total_seconds()) < 5


@pytest.mark.asyncio
async def test_send_queued_email_marks_completed_after_last_follow_up_step(
    db_session, scheduling_setup, fake_provider
):
    from app.workers.tasks import _send_queued_email_async

    cc = scheduling_setup["campaign_contact"]
    cc.current_step = 2  # past both entries in follow_up_schedule_days=[4, 9]
    cc.generated_email_history = [_passing_draft(step_number=2)]
    await db_session.commit()

    await _send_queued_email_async(cc.id)

    await db_session.refresh(cc)
    assert cc.status == CampaignContactStatus.completed


@pytest.mark.asyncio
async def test_send_queued_email_is_idempotent_under_duplicate_dispatch(
    db_session, scheduling_setup, fake_provider
):
    """Simulates the same task landing twice (e.g. a broker redelivery): the second
    call must be a no-op because the Redis lock is still held."""
    from app.workers.tasks import _send_queued_email_async

    cc = scheduling_setup["campaign_contact"]

    await _send_queued_email_async(cc.id)
    await _send_queued_email_async(cc.id)

    assert len(fake_provider.send_calls) == 1
    messages = (
        (await db_session.execute(select(EmailMessage).where(EmailMessage.campaign_contact_id == cc.id)))
        .scalars()
        .all()
    )
    assert len(messages) == 1


@pytest.mark.asyncio
async def test_send_queued_email_rechecks_suppression_and_never_calls_provider(
    db_session, scheduling_setup, fake_provider
):
    from app.workers.tasks import _send_queued_email_async

    cc = scheduling_setup["campaign_contact"]
    await add_suppression(
        db_session, "jamie@example.com", SuppressionReason.manual_block, SuppressionSource.user
    )
    await db_session.commit()

    await _send_queued_email_async(cc.id)

    assert fake_provider.send_calls == []
    await db_session.refresh(cc)
    assert cc.status == CampaignContactStatus.suppressed
    messages = (
        (await db_session.execute(select(EmailMessage).where(EmailMessage.campaign_contact_id == cc.id)))
        .scalars()
        .all()
    )
    assert messages == []


@pytest.mark.asyncio
async def test_send_queued_email_refuses_to_send_a_draft_that_fails_the_quality_gate(
    db_session, scheduling_setup, fake_provider
):
    """Belt-and-suspenders: approve() already enforces this, but the send path must
    never trust that invariant blindly."""
    from app.workers.tasks import _send_queued_email_async

    cc = scheduling_setup["campaign_contact"]
    bad_draft = _passing_draft(step_number=0)
    bad_draft["quality_gate"] = {"passed": False, "failures": ["too short"]}
    cc.generated_email_history = [bad_draft]
    await db_session.commit()

    await _send_queued_email_async(cc.id)

    assert fake_provider.send_calls == []
    messages = (
        (await db_session.execute(select(EmailMessage).where(EmailMessage.campaign_contact_id == cc.id)))
        .scalars()
        .all()
    )
    assert messages == []


@pytest.mark.asyncio
async def test_send_queued_email_threads_follow_up_off_the_prior_message(
    db_session, redis_client, scheduling_setup, fake_provider
):
    """The second send for the same contact should reference the first message for
    proper email threading (thread_id / in-reply-to)."""
    from app.workers.tasks import _send_queued_email_async

    cc = scheduling_setup["campaign_contact"]
    await _send_queued_email_async(cc.id)

    await db_session.refresh(cc)
    # It's now step 1, pending review again — simulate operator approval of the
    # follow-up draft and make it due immediately.
    cc.generated_email_history = [*cc.generated_email_history, _passing_draft(step_number=1)]
    cc.status = CampaignContactStatus.queued
    cc.next_action_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    # In production the two sends are days apart, so the first send's idempotency
    # lock (600s TTL) has long since expired by the time the follow-up is due.
    await redis_client.delete(f"send_lock:{cc.id}")

    await _send_queued_email_async(cc.id)

    assert len(fake_provider.send_calls) == 2
    second_request = fake_provider.send_calls[1]
    assert second_request.thread_id == "fake-thread-id"
    assert second_request.in_reply_to_message_id == "fake-msg-id"
