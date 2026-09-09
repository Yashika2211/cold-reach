import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.core.logging import get_logger
from app.core.redis import new_redis_client
from app.db.session import AsyncSessionLocal, engine
from app.models import Campaign, CampaignContact, Contact, EmailMessage, EventLog
from app.models.enums import CampaignContactStatus
from app.providers.email.base import SendEmailRequest
from app.services.campaign_contacts import generate_draft, get_current_draft
from app.services.scheduler import (
    acquire_send_lock,
    get_active_campaigns,
    get_eligible_contacts,
    get_remaining_quota,
    is_globally_paused,
    is_within_send_window,
    random_jitter_seconds,
    reserve_quota_slot,
)
from app.services.sending_accounts import build_provider
from app.services.suppression import is_suppressed

logger = get_logger(__name__)


@celery_app.task(name="app.workers.tasks.ping")
def ping() -> str:
    return "pong"


@celery_app.task(
    name="app.workers.tasks.generate_campaign_contact_draft",
    autoretry_for=(Exception,),
    retry_backoff=5,
    retry_kwargs={"max_retries": 2},
)
def generate_campaign_contact_draft(campaign_contact_id: str) -> None:
    """Pre-generates the initial draft for a CampaignContact so the review queue
    is instant to page through instead of waiting on an LLM call per card."""
    asyncio.run(_generate_campaign_contact_draft_async(uuid.UUID(campaign_contact_id)))


async def _generate_campaign_contact_draft_async(campaign_contact_id: uuid.UUID) -> None:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CampaignContact)
                .options(
                    selectinload(CampaignContact.campaign),
                    selectinload(CampaignContact.contact),
                )
                .where(CampaignContact.id == campaign_contact_id)
            )
            campaign_contact = result.scalar_one_or_none()
            if campaign_contact is None:
                logger.warning(
                    "campaign_contact_not_found", campaign_contact_id=str(campaign_contact_id)
                )
                return

            if get_current_draft(campaign_contact) is not None:
                return  # already generated (e.g. task retried after a partial failure)

            await generate_draft(db, campaign_contact)
            await db.commit()
    finally:
        # See the matching comment in _scheduler_tick_async: a pooled asyncpg
        # connection is bound to the event loop that opened it, and this task's
        # asyncio.run() gives it a fresh loop every invocation.
        await engine.dispose()


@celery_app.task(name="app.workers.tasks.scheduler_tick")
def scheduler_tick() -> None:
    """Runs every 60s via Celery Beat. Never sends anything itself — only decides
    which approved, due, in-window, under-quota contacts get a send task queued,
    each with its own randomized jitter delay."""
    asyncio.run(_scheduler_tick_async())


async def _scheduler_tick_async() -> None:
    # Freshly created per call rather than the app-wide cached client: this runs
    # inside its own asyncio.run() event loop each tick, and a client cached across
    # loops holds a connection bound to a now-closed loop by the next tick.
    redis = new_redis_client()
    try:
        if await is_globally_paused(redis):
            return

        async with AsyncSessionLocal() as db:
            campaigns = await get_active_campaigns(db)

            for campaign in campaigns:
                if not is_within_send_window(campaign):
                    continue

                await db.refresh(campaign, attribute_names=["sending_account"])
                sending_account = campaign.sending_account
                if not sending_account.is_active:
                    continue

                remaining = await get_remaining_quota(redis, campaign, sending_account)
                if remaining <= 0:
                    continue

                eligible = await get_eligible_contacts(db, campaign, limit=remaining)

                for cc in eligible:
                    if await is_suppressed(db, cc.contact.email):
                        cc.status = CampaignContactStatus.suppressed
                        continue

                    await reserve_quota_slot(redis, campaign, sending_account)
                    jitter = random_jitter_seconds()
                    send_queued_email.apply_async(args=[str(cc.id)], countdown=jitter)
                    logger.info(
                        "scheduled_send",
                        campaign_contact_id=str(cc.id),
                        campaign_id=str(campaign.id),
                        jitter_seconds=jitter,
                    )

            await db.commit()
    finally:
        await redis.aclose()
        # The shared engine's pooled connections are asyncpg connections bound to
        # the event loop that opened them. Since this whole function runs inside
        # its own asyncio.run() loop, a connection left in the pool at loop-close
        # would break (even under pool_pre_ping) on the next task's new loop with
        # "Future attached to a different loop". Disposing here forces a clean pool
        # for whichever task runs next.
        await engine.dispose()


@celery_app.task(name="app.workers.tasks.send_queued_email")
def send_queued_email(campaign_contact_id: str) -> None:
    asyncio.run(_send_queued_email_async(uuid.UUID(campaign_contact_id)))


async def _send_queued_email_async(campaign_contact_id: uuid.UUID) -> None:
    # See the comment in _scheduler_tick_async: must be a fresh client per
    # asyncio.run()-scoped call, not the app-wide cached one.
    redis = new_redis_client()
    try:
        if not await acquire_send_lock(redis, campaign_contact_id):
            logger.info(
                "send_lock_not_acquired_skipping", campaign_contact_id=str(campaign_contact_id)
            )
            return

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CampaignContact)
                .options(
                    selectinload(CampaignContact.campaign).selectinload(Campaign.sending_account),
                    selectinload(CampaignContact.contact).selectinload(Contact.company),
                )
                .where(CampaignContact.id == campaign_contact_id)
            )
            cc = result.scalar_one_or_none()
            if cc is None:
                return

            # Race guard: something else (a manual skip/suppress, a concurrent tick)
            # may have moved this contact on since it was scheduled.
            if cc.status != CampaignContactStatus.queued:
                return

            if await is_suppressed(db, cc.contact.email):
                cc.status = CampaignContactStatus.suppressed
                await db.commit()
                return

            draft = get_current_draft(cc)
            if draft is None or not draft["quality_gate"]["passed"]:
                # Shouldn't happen — approve() already enforced this — but never
                # send something that failed its own quality gate.
                logger.error(
                    "send_blocked_failed_quality_gate", campaign_contact_id=str(campaign_contact_id)
                )
                return

            campaign = cc.campaign
            sending_account = campaign.sending_account

            prior_message_result = await db.execute(
                select(EmailMessage)
                .where(EmailMessage.campaign_contact_id == cc.id)
                .order_by(EmailMessage.sent_at.desc())
                .limit(1)
            )
            prior_message = prior_message_result.scalar_one_or_none()

            provider = build_provider(sending_account, db)
            request = SendEmailRequest(
                to_email=cc.contact.email,
                to_name=(
                    " ".join(filter(None, [cc.contact.first_name, cc.contact.last_name])) or None
                ),
                subject=draft["subject"],
                body_text=draft["body"],
                from_email=sending_account.from_address,
                from_name=sending_account.display_name,
                reply_to=sending_account.from_address,
                thread_id=prior_message.thread_id if prior_message else None,
                in_reply_to_message_id=(
                    prior_message.provider_message_id if prior_message else None
                ),
            )

            try:
                result = await provider.send(request)
            except Exception:
                logger.exception("send_failed", campaign_contact_id=str(campaign_contact_id))
                raise

            sent_at = datetime.now(UTC)
            email_message = EmailMessage(
                campaign_contact_id=cc.id,
                sending_account_id=sending_account.id,
                step_number=cc.current_step,
                to_email=cc.contact.email,
                subject=draft["subject"],
                body=draft["body"],
                provider_message_id=result.provider_message_id,
                thread_id=result.thread_id,
                sent_at=sent_at,
            )
            db.add(email_message)

            db.add(
                EventLog(
                    entity_type="campaign_contact",
                    entity_id=cc.id,
                    event_type="sent",
                    payload={
                        "campaign_id": str(campaign.id),
                        "step_number": cc.current_step,
                        "provider_message_id": result.provider_message_id,
                    },
                )
            )

            campaign.sent_count += 1

            next_step_index = cc.current_step  # 0-indexed step just sent
            follow_up_days = campaign.follow_up_schedule_days
            if next_step_index < len(follow_up_days):
                cc.current_step = cc.current_step + 1
                cc.next_action_at = sent_at + timedelta(days=follow_up_days[next_step_index])
                cc.status = CampaignContactStatus.pending
            else:
                cc.status = CampaignContactStatus.completed

            await db.commit()
    finally:
        await redis.aclose()
        await engine.dispose()
