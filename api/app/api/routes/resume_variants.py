import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.config import get_settings
from app.db.session import get_db
from app.models import ResumeVariant
from app.schemas.resume_variant import ResumeVariantCreate, ResumeVariantRead, ResumeVariantUpdate

router = APIRouter(
    prefix="/resume-variants", tags=["resume-variants"], dependencies=[Depends(get_current_admin)]
)

MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB


def _to_read(variant: ResumeVariant) -> ResumeVariantRead:
    return ResumeVariantRead(
        id=variant.id,
        name=variant.name,
        role_family=variant.role_family,
        positioning_summary=variant.positioning_summary,
        highlight_projects=variant.highlight_projects,
        is_default=variant.is_default,
        has_pdf=bool(variant.pdf_file_path),
        created_at=variant.created_at,
        updated_at=variant.updated_at,
    )


async def _get_or_404(db: AsyncSession, variant_id: uuid.UUID) -> ResumeVariant:
    result = await db.execute(
        select(ResumeVariant).where(
            ResumeVariant.id == variant_id, ResumeVariant.deleted_at.is_(None)
        )
    )
    variant = result.scalar_one_or_none()
    if variant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume variant not found")
    return variant


async def _clear_other_defaults(db: AsyncSession, role_family: str | None, except_id: uuid.UUID) -> None:
    if role_family is None:
        return
    result = await db.execute(
        select(ResumeVariant).where(
            ResumeVariant.role_family == role_family,
            ResumeVariant.id != except_id,
            ResumeVariant.deleted_at.is_(None),
        )
    )
    for other in result.scalars().all():
        other.is_default = False


@router.get("", response_model=list[ResumeVariantRead])
async def list_resume_variants(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ResumeVariant)
        .where(ResumeVariant.deleted_at.is_(None))
        .order_by(ResumeVariant.created_at.desc())
    )
    return [_to_read(v) for v in result.scalars().all()]


@router.post("", response_model=ResumeVariantRead, status_code=status.HTTP_201_CREATED)
async def create_resume_variant(payload: ResumeVariantCreate, db: AsyncSession = Depends(get_db)):
    variant = ResumeVariant(**payload.model_dump())
    db.add(variant)
    await db.flush()
    if payload.is_default:
        await _clear_other_defaults(db, payload.role_family, variant.id)
    await db.commit()
    await db.refresh(variant)
    return _to_read(variant)


@router.get("/{variant_id}", response_model=ResumeVariantRead)
async def get_resume_variant(variant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return _to_read(await _get_or_404(db, variant_id))


@router.patch("/{variant_id}", response_model=ResumeVariantRead)
async def update_resume_variant(
    variant_id: uuid.UUID, payload: ResumeVariantUpdate, db: AsyncSession = Depends(get_db)
):
    variant = await _get_or_404(db, variant_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(variant, field, value)
    await db.flush()
    if payload.is_default:
        await _clear_other_defaults(db, variant.role_family, variant.id)
    await db.commit()
    await db.refresh(variant, attribute_names=["updated_at"])
    return _to_read(variant)


@router.delete("/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume_variant(variant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    variant = await _get_or_404(db, variant_id)
    variant.deleted_at = datetime.now(UTC)
    await db.commit()


@router.post("/{variant_id}/upload", response_model=ResumeVariantRead)
async def upload_resume_pdf(
    variant_id: uuid.UUID, file: UploadFile, db: AsyncSession = Depends(get_db)
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")

    contents = await file.read(MAX_PDF_BYTES + 1)
    if len(contents) > MAX_PDF_BYTES:
        raise HTTPException(status_code=400, detail="PDF exceeds the 10MB limit")

    variant = await _get_or_404(db, variant_id)

    storage_dir = Path(get_settings().resume_storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = storage_dir / f"{variant.id}.pdf"
    file_path.write_bytes(contents)

    variant.pdf_file_path = str(file_path)
    await db.commit()
    await db.refresh(variant, attribute_names=["updated_at"])
    return _to_read(variant)


@router.get("/{variant_id}/file")
async def download_resume_pdf(variant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    variant = await _get_or_404(db, variant_id)
    if not variant.pdf_file_path or not Path(variant.pdf_file_path).exists():
        raise HTTPException(status_code=404, detail="No PDF uploaded for this resume variant")
    return FileResponse(
        variant.pdf_file_path, media_type="application/pdf", filename=f"{variant.name}.pdf"
    )
