import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models import Company
from app.schemas.common import Page
from app.schemas.company import CompanyCreate, CompanyRead, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["companies"], dependencies=[Depends(get_current_admin)])


async def _get_company_or_404(db: AsyncSession, company_id: uuid.UUID) -> Company:
    result = await db.execute(
        select(Company).where(Company.id == company_id, Company.deleted_at.is_(None))
    )
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.get("", response_model=Page[CompanyRead])
async def list_companies(
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(Company).where(Company.deleted_at.is_(None))
    count_query = select(func.count()).select_from(Company).where(Company.deleted_at.is_(None))

    if search:
        pattern = f"%{search}%"
        clause = or_(Company.name.ilike(pattern), Company.domain.ilike(pattern))
        query = query.where(clause)
        count_query = count_query.where(clause)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(Company.name).limit(limit).offset(offset))
    companies = result.scalars().all()

    return Page(items=companies, total=total, limit=limit, offset=offset)


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
async def create_company(payload: CompanyCreate, db: AsyncSession = Depends(get_db)):
    company = Company(**payload.model_dump())
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company


@router.get("/{company_id}", response_model=CompanyRead)
async def get_company(company_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _get_company_or_404(db, company_id)


@router.patch("/{company_id}", response_model=CompanyRead)
async def update_company(
    company_id: uuid.UUID, payload: CompanyUpdate, db: AsyncSession = Depends(get_db)
):
    company = await _get_company_or_404(db, company_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    await db.commit()
    await db.refresh(company)
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(company_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    company = await _get_company_or_404(db, company_id)
    company.deleted_at = datetime.now(UTC)
    await db.commit()
