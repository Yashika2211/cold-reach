import random
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Campaign, CampaignContact, Contact, EmailMessage, SendingAccount
from app.models.enums import CampaignContactStatus, CampaignStatus

JITTER_MIN_SECONDS = 45
JITTER_MAX_SECONDS = 180
SEND_LOCK_TTL_SECONDS = 600
GLOBAL_PAUSE_KEY = "scheduling:global_pause"


def random_jitter_seconds() -> int:
    return random.randint(JITTER_MIN_SECONDS, JITTER_MAX_SECONDS)


async def is_globally_paused(redis: Redis) -> bool:
    return bool(await redis.get(GLOBAL_PAUSE_KEY))


async def set_global_pause(redis: Redis, paused: bool) -> None:
    if paused:
        await redis.set(GLOBAL_PAUSE_KEY, "1")
    else:
        await redis.delete(GLOBAL_PAUSE_KEY)


def _local_today(tz_name: str) -> date:
    return datetime.now(ZoneInfo(tz_name)).date()


def is_within_send_window(campaign: Campaign, now: datetime | None = None) -> bool:
    tz = ZoneInfo(campaign.timezone)
    local_now = (now or datetime.now(UTC)).astimezone(tz)

    if local_now.weekday() not in campaign.send_window_days:
        return False

    current_time = local_now.time()
    return campaign.send_window_start_local <= current_time <= campaign.send_window_end_local


def _quota_keys(campaign: Campaign, sending_account_id) -> tuple[str, str]:
    today = _local_today(campaign.timezone).isoformat()
    campaign_key = f"quota:campaign:{campaign.id}:{today}"
    account_key = f"quota:account:{sending_account_id}:{today}"
    return campaign_key, account_key


async def get_remaining_quota(redis: Redis, campaign: Campaign, sending_account: SendingAccount) -> int:
    campaign_key, account_key = _quota_keys(campaign, sending_account.id)
    campaign_sent = int(await redis.get(campaign_key) or 0)
    account_sent = int(await redis.get(account_key) or 0)

    remaining_for_campaign = campaign.daily_cap - campaign_sent
    remaining_for_account = sending_account.daily_cap - account_sent
    return max(0, min(remaining_for_campaign, remaining_for_account))


async def reserve_quota_slot(redis: Redis, campaign: Campaign, sending_account: SendingAccount) -> None:
    """Reserved at scheduling time (not after the send completes) so a burst of ticks
    can never overcommit past the cap while sends are still in their jitter delay."""
    campaign_key, account_key = _quota_keys(campaign, sending_account.id)
    seconds_until_midnight = 25 * 60 * 60  # generous TTL; keys are date-suffixed anyway
    pipe = redis.pipeline()
    pipe.incr(campaign_key)
    pipe.expire(campaign_key, seconds_until_midnight)
    pipe.incr(account_key)
    pipe.expire(account_key, seconds_until_midnight)
    await pipe.execute()


async def acquire_send_lock(redis: Redis, campaign_contact_id) -> bool:
    return bool(await redis.set(f"send_lock:{campaign_contact_id}", "1", nx=True, ex=SEND_LOCK_TTL_SECONDS))


async def get_active_campaigns(db: AsyncSession) -> list[Campaign]:
    result = await db.execute(
        select(Campaign).where(Campaign.status == CampaignStatus.active, Campaign.deleted_at.is_(None))
    )
    return list(result.scalars().all())


async def get_eligible_contacts(db: AsyncSession, campaign: Campaign, limit: int) -> list[CampaignContact]:
    now = datetime.now(UTC)
    result = await db.execute(
        select(CampaignContact)
        .options(selectinload(CampaignContact.contact).selectinload(Contact.company))
        .where(
            CampaignContact.campaign_id == campaign.id,
            CampaignContact.status == CampaignContactStatus.queued,
            CampaignContact.next_action_at.is_not(None),
            CampaignContact.next_action_at <= now,
            CampaignContact.deleted_at.is_(None),
        )
        .order_by(CampaignContact.next_action_at)
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_sent_today_for_account(db: AsyncSession, sending_account_id, tz_name: str) -> int:
    """Redis quota counters are the source of truth during a running session, but this
    gives an independent DB-backed number for display/testing without relying on Redis
    state surviving a restart."""
    today_start = datetime.combine(_local_today(tz_name), datetime.min.time(), tzinfo=ZoneInfo(tz_name))
    result = await db.execute(
        select(func.count())
        .select_from(EmailMessage)
        .where(EmailMessage.sending_account_id == sending_account_id, EmailMessage.sent_at >= today_start)
    )
    return result.scalar_one()
