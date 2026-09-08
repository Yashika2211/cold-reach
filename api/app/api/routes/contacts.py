import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models import Contact
from app.models.enums import ContactSource, ContactStatus, SuppressionReason, SuppressionSource
from app.schemas.common import Page
from app.schemas.contact import ContactCreate, ContactRead, ContactUpdate
from app.services.email_utils import normalize_email
from app.services.suppression import add_suppression, get_suppressed_set

router = APIRouter(prefix="/contacts", tags=["contacts"], dependencies=[Depends(get_current_admin)])


def _to_read(contact: Contact, suppressed: set[str]) -> ContactRead:
    return ContactRead(
        id=contact.id,
        first_name=contact.first_name,
        last_name=contact.last_name,
        email=contact.email,
        normalized_email=contact.normalized_email,
        title=contact.title,
        company_id=contact.company_id,
        company_name=contact.company.name if contact.company else None,
        linkedin_url=contact.linkedin_url,
        notes=contact.notes,
        source=contact.source,
        verification_status=contact.verification_status,
        confidence_score=contact.confidence_score,
        status=contact.status,
        is_suppressed=contact.normalized_email in suppressed,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


async def _get_contact_or_404(db: AsyncSession, contact_id: uuid.UUID) -> Contact:
    result = await db.execute(
        select(Contact)
        .options(selectinload(Contact.company))
        .where(Contact.id == contact_id, Contact.deleted_at.is_(None))
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    return contact


@router.get("", response_model=Page[ContactRead])
async def list_contacts(
    search: str | None = None,
    status_filter: ContactStatus | None = Query(default=None, alias="status"),
    source: ContactSource | None = None,
    company_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    filters = [Contact.deleted_at.is_(None)]
    if status_filter:
        filters.append(Contact.status == status_filter)
    if source:
        filters.append(Contact.source == source)
    if company_id:
        filters.append(Contact.company_id == company_id)
    if search:
        pattern = f"%{search}%"
        filters.append(
            or_(
                Contact.first_name.ilike(pattern),
                Contact.last_name.ilike(pattern),
                Contact.email.ilike(pattern),
                Contact.title.ilike(pattern),
            )
        )

    count_query = select(func.count()).select_from(Contact).where(*filters)
    total = (await db.execute(count_query)).scalar_one()

    query = (
        select(Contact)
        .options(selectinload(Contact.company))
        .where(*filters)
        .order_by(Contact.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    contacts = (await db.execute(query)).scalars().all()

    suppressed = await get_suppressed_set(db, [c.email for c in contacts])
    items = [_to_read(c, suppressed) for c in contacts]

    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
async def create_contact(payload: ContactCreate, db: AsyncSession = Depends(get_db)):
    normalized = normalize_email(payload.email)

    existing = await db.execute(
        select(Contact.id).where(Contact.normalized_email == normalized, Contact.deleted_at.is_(None))
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A contact with this email already exists"
        )

    contact = Contact(
        **payload.model_dump(),
        normalized_email=normalized,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact, attribute_names=["company", "updated_at"])

    suppressed = await get_suppressed_set(db, [contact.email])
    return _to_read(contact, suppressed)


@router.get("/{contact_id}", response_model=ContactRead)
async def get_contact(contact_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    contact = await _get_contact_or_404(db, contact_id)
    suppressed = await get_suppressed_set(db, [contact.email])
    return _to_read(contact, suppressed)


@router.patch("/{contact_id}", response_model=ContactRead)
async def update_contact(
    contact_id: uuid.UUID, payload: ContactUpdate, db: AsyncSession = Depends(get_db)
):
    contact = await _get_contact_or_404(db, contact_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    await db.commit()
    await db.refresh(contact, attribute_names=["company", "updated_at"])

    suppressed = await get_suppressed_set(db, [contact.email])
    return _to_read(contact, suppressed)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(contact_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    contact = await _get_contact_or_404(db, contact_id)
    contact.deleted_at = datetime.now(UTC)
    await db.commit()


class BulkContactIds(BaseModel):
    contact_ids: list[uuid.UUID]


@router.post("/bulk-suppress", response_model=dict)
async def bulk_suppress(payload: BulkContactIds, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Contact).where(Contact.id.in_(payload.contact_ids), Contact.deleted_at.is_(None))
    )
    contacts = result.scalars().all()

    for contact in contacts:
        await add_suppression(
            db, contact.email, reason=SuppressionReason.manual_block, source=SuppressionSource.user
        )
        contact.status = ContactStatus.suppressed

    await db.commit()
    return {"suppressed": len(contacts)}
