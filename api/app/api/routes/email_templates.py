import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models import EmailTemplate
from app.schemas.email_template import EmailTemplateCreate, EmailTemplateRead, EmailTemplateUpdate

router = APIRouter(
    prefix="/email-templates", tags=["email-templates"], dependencies=[Depends(get_current_admin)]
)


async def _get_or_404(db: AsyncSession, template_id: uuid.UUID) -> EmailTemplate:
    result = await db.execute(
        select(EmailTemplate).where(
            EmailTemplate.id == template_id, EmailTemplate.deleted_at.is_(None)
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return template


@router.get("", response_model=list[EmailTemplateRead])
async def list_email_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EmailTemplate)
        .where(EmailTemplate.deleted_at.is_(None))
        .order_by(EmailTemplate.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=EmailTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_email_template(payload: EmailTemplateCreate, db: AsyncSession = Depends(get_db)):
    template = EmailTemplate(**payload.model_dump())
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.get("/{template_id}", response_model=EmailTemplateRead)
async def get_email_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _get_or_404(db, template_id)


@router.patch("/{template_id}", response_model=EmailTemplateRead)
async def update_email_template(
    template_id: uuid.UUID, payload: EmailTemplateUpdate, db: AsyncSession = Depends(get_db)
):
    template = await _get_or_404(db, template_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    await db.commit()
    await db.refresh(template, attribute_names=["updated_at"])
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_email_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    template = await _get_or_404(db, template_id)
    template.deleted_at = datetime.now(UTC)
    await db.commit()
