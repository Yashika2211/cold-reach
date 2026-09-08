import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models import SuppressionEntry
from app.models.enums import SuppressionSource
from app.schemas.common import Page
from app.schemas.suppression import SuppressionCreate, SuppressionRead
from app.services.suppression import add_suppression

router = APIRouter(
    prefix="/suppression", tags=["suppression"], dependencies=[Depends(get_current_admin)]
)


@router.get("", response_model=Page[SuppressionRead])
async def list_suppression(
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(SuppressionEntry)
    count_query = select(func.count()).select_from(SuppressionEntry)

    if search:
        pattern = f"%{search}%"
        query = query.where(SuppressionEntry.email.ilike(pattern))
        count_query = count_query.where(SuppressionEntry.email.ilike(pattern))

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(
        query.order_by(SuppressionEntry.created_at.desc()).limit(limit).offset(offset)
    )
    entries = result.scalars().all()

    return Page(items=entries, total=total, limit=limit, offset=offset)


@router.post("", response_model=SuppressionRead, status_code=status.HTTP_201_CREATED)
async def create_suppression(payload: SuppressionCreate, db: AsyncSession = Depends(get_db)):
    entry = await add_suppression(
        db, payload.email, reason=payload.reason, source=SuppressionSource.user
    )
    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_suppression(entry_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SuppressionEntry).where(SuppressionEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suppression entry not found")
    await db.delete(entry)
    await db.commit()
