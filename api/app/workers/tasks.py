import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models import CampaignContact
from app.services.campaign_contacts import generate_draft, get_current_draft

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
            logger.warning("campaign_contact_not_found", campaign_contact_id=str(campaign_contact_id))
            return

        if get_current_draft(campaign_contact) is not None:
            return  # already generated (e.g. task retried after a partial failure)

        await generate_draft(db, campaign_contact)
        await db.commit()
