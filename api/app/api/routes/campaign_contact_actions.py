import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models import CampaignContact, Contact
from app.models.enums import CampaignContactStatus, SuppressionReason, SuppressionSource
from app.providers.llm.base import LLMProviderError
from app.schemas.campaign import CampaignContactRead, HandEditRequest, RegenerateRequest
from app.services.campaign_contacts import (
    NoDraftError,
    QualityGateFailedError,
    generate_draft,
    hand_edit_draft,
    to_campaign_contact_read,
)
from app.services.campaign_contacts import (
    approve as approve_campaign_contact,
)
from app.services.campaign_contacts import (
    skip as skip_campaign_contact,
)
from app.services.suppression import add_suppression

router = APIRouter(
    prefix="/campaign-contacts", tags=["campaigns"], dependencies=[Depends(get_current_admin)]
)


async def _get_or_404(db: AsyncSession, campaign_contact_id: uuid.UUID) -> CampaignContact:
    result = await db.execute(
        select(CampaignContact)
        .options(
            selectinload(CampaignContact.contact).selectinload(Contact.company),
            selectinload(CampaignContact.campaign),
        )
        .where(CampaignContact.id == campaign_contact_id, CampaignContact.deleted_at.is_(None))
    )
    cc = result.scalar_one_or_none()
    if cc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign contact not found")
    return cc


@router.post("/{campaign_contact_id}/approve", response_model=CampaignContactRead)
async def approve(campaign_contact_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    cc = await _get_or_404(db, campaign_contact_id)
    try:
        approve_campaign_contact(cc)
    except NoDraftError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except QualityGateFailedError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(cc, attribute_names=["updated_at"])
    return to_campaign_contact_read(cc)


@router.post("/{campaign_contact_id}/regenerate", response_model=CampaignContactRead)
async def regenerate(
    campaign_contact_id: uuid.UUID, payload: RegenerateRequest, db: AsyncSession = Depends(get_db)
):
    cc = await _get_or_404(db, campaign_contact_id)
    try:
        await generate_draft(db, cc, steering_note=payload.steering_note, source="regenerated")
    except LLMProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Regeneration failed: {exc}"
        ) from exc
    await db.commit()
    await db.refresh(cc, attribute_names=["updated_at"])
    return to_campaign_contact_read(cc)


@router.patch("/{campaign_contact_id}/edit", response_model=CampaignContactRead)
async def hand_edit(
    campaign_contact_id: uuid.UUID, payload: HandEditRequest, db: AsyncSession = Depends(get_db)
):
    cc = await _get_or_404(db, campaign_contact_id)
    await hand_edit_draft(cc, payload.subject, payload.body)
    await db.commit()
    await db.refresh(cc, attribute_names=["updated_at"])
    return to_campaign_contact_read(cc)


@router.post("/{campaign_contact_id}/skip", response_model=CampaignContactRead)
async def skip(campaign_contact_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    cc = await _get_or_404(db, campaign_contact_id)
    skip_campaign_contact(cc)
    await db.commit()
    await db.refresh(cc, attribute_names=["updated_at"])
    return to_campaign_contact_read(cc)


@router.post("/{campaign_contact_id}/suppress", response_model=CampaignContactRead)
async def suppress(campaign_contact_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    cc = await _get_or_404(db, campaign_contact_id)
    await add_suppression(
        db, cc.contact.email, reason=SuppressionReason.manual_block, source=SuppressionSource.user
    )
    cc.status = CampaignContactStatus.suppressed
    await db.commit()
    await db.refresh(cc, attribute_names=["updated_at"])
    return to_campaign_contact_read(cc)
