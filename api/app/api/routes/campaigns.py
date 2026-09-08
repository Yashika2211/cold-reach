import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin
from app.core.logging import get_logger
from app.db.session import get_db
from app.models import Campaign, CampaignContact, Contact
from app.models.enums import CampaignContactStatus
from app.schemas.campaign import (
    AddContactsRequest,
    AddContactsResponse,
    CampaignContactRead,
    CampaignCreate,
    CampaignFunnel,
    CampaignRead,
    CampaignUpdate,
    ReviewQueueResponse,
)
from app.services.campaign_contacts import generate_draft, get_current_draft, to_campaign_contact_read

router = APIRouter(prefix="/campaigns", tags=["campaigns"], dependencies=[Depends(get_current_admin)])
logger = get_logger(__name__)


async def _get_campaign_or_404(db: AsyncSession, campaign_id: uuid.UUID) -> Campaign:
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.deleted_at.is_(None))
    )
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign




@router.get("", response_model=list[CampaignRead])
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Campaign).where(Campaign.deleted_at.is_(None)).order_by(Campaign.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
async def create_campaign(payload: CampaignCreate, db: AsyncSession = Depends(get_db)):
    campaign = Campaign(**payload.model_dump())
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.get("/{campaign_id}", response_model=CampaignRead)
async def get_campaign(campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _get_campaign_or_404(db, campaign_id)


@router.patch("/{campaign_id}", response_model=CampaignRead)
async def update_campaign(
    campaign_id: uuid.UUID, payload: CampaignUpdate, db: AsyncSession = Depends(get_db)
):
    campaign = await _get_campaign_or_404(db, campaign_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(campaign, field, value)
    await db.commit()
    await db.refresh(campaign, attribute_names=["updated_at"])
    return campaign


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    campaign = await _get_campaign_or_404(db, campaign_id)
    campaign.deleted_at = datetime.now(UTC)
    await db.commit()


@router.post("/{campaign_id}/contacts", response_model=AddContactsResponse)
async def add_contacts(
    campaign_id: uuid.UUID, payload: AddContactsRequest, db: AsyncSession = Depends(get_db)
):
    campaign = await _get_campaign_or_404(db, campaign_id)

    existing_result = await db.execute(
        select(CampaignContact.contact_id).where(CampaignContact.campaign_id == campaign.id)
    )
    existing_ids = set(existing_result.scalars().all())

    valid_result = await db.execute(
        select(Contact.id).where(
            Contact.id.in_(payload.contact_ids), Contact.deleted_at.is_(None)
        )
    )
    valid_ids = set(valid_result.scalars().all())

    new_ids = [cid for cid in payload.contact_ids if cid not in existing_ids and cid in valid_ids]

    created_ccs = []
    for contact_id in new_ids:
        cc = CampaignContact(campaign_id=campaign.id, contact_id=contact_id)
        db.add(cc)
        created_ccs.append(cc)

    await db.commit()

    for cc in created_ccs:
        await db.refresh(cc)
        try:
            from app.workers.tasks import generate_campaign_contact_draft

            generate_campaign_contact_draft.delay(str(cc.id))
        except Exception:
            # Celery/Redis unavailable — the review queue falls back to sync generation,
            # so this is degraded performance, not a broken feature.
            logger.warning("campaign_contact_predraft_dispatch_failed", campaign_contact_id=str(cc.id))

    skipped_existing = len(existing_ids & set(payload.contact_ids))
    return AddContactsResponse(added=len(created_ccs), skipped_existing=skipped_existing)


@router.get("/{campaign_id}/contacts", response_model=list[CampaignContactRead])
async def list_campaign_contacts(
    campaign_id: uuid.UUID,
    status_filter: CampaignContactStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    await _get_campaign_or_404(db, campaign_id)

    filters = [CampaignContact.campaign_id == campaign_id, CampaignContact.deleted_at.is_(None)]
    if status_filter:
        filters.append(CampaignContact.status == status_filter)

    result = await db.execute(
        select(CampaignContact)
        .options(selectinload(CampaignContact.contact))
        .where(*filters)
        .order_by(CampaignContact.created_at)
        .limit(limit)
        .offset(offset)
    )
    return [to_campaign_contact_read(cc) for cc in result.scalars().all()]


@router.get("/{campaign_id}/funnel", response_model=CampaignFunnel)
async def campaign_funnel(campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _get_campaign_or_404(db, campaign_id)

    result = await db.execute(
        select(CampaignContact.status, func.count())
        .where(CampaignContact.campaign_id == campaign_id, CampaignContact.deleted_at.is_(None))
        .group_by(CampaignContact.status)
    )
    by_status = {status_val.value: count for status_val, count in result.all()}
    return CampaignFunnel(total=sum(by_status.values()), by_status=by_status)


@router.get("/{campaign_id}/review-queue/next", response_model=ReviewQueueResponse)
async def review_queue_next(campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _get_campaign_or_404(db, campaign_id)

    count_result = await db.execute(
        select(func.count()).where(
            CampaignContact.campaign_id == campaign_id,
            CampaignContact.status == CampaignContactStatus.pending,
            CampaignContact.deleted_at.is_(None),
        )
    )
    remaining = count_result.scalar_one()

    result = await db.execute(
        select(CampaignContact)
        .options(selectinload(CampaignContact.contact), selectinload(CampaignContact.campaign))
        .where(
            CampaignContact.campaign_id == campaign_id,
            CampaignContact.status == CampaignContactStatus.pending,
            CampaignContact.deleted_at.is_(None),
        )
        .order_by(CampaignContact.created_at)
        .limit(1)
    )
    cc = result.scalar_one_or_none()

    if cc is None:
        return ReviewQueueResponse(campaign_contact=None, remaining=0)

    if get_current_draft(cc) is None:
        await generate_draft(db, cc)
        await db.commit()
        await db.refresh(cc, attribute_names=["updated_at"])

    return ReviewQueueResponse(campaign_contact=to_campaign_contact_read(cc), remaining=remaining)
