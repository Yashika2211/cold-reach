import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.schemas.generation import GenerationResult
from app.services.email_generation import assemble_context, generate_email

router = APIRouter(
    prefix="/email-generation", tags=["email-generation"], dependencies=[Depends(get_current_admin)]
)


class GenerationRequest(BaseModel):
    contact_id: uuid.UUID
    resume_variant_id: uuid.UUID
    template_id: uuid.UUID
    step_number: int = 0
    job_opening_id: uuid.UUID | None = None
    steering_note: str | None = None


@router.post("/preview", response_model=GenerationResult)
async def preview_generation(payload: GenerationRequest, db: AsyncSession = Depends(get_db)):
    ctx = await assemble_context(
        db,
        contact_id=payload.contact_id,
        resume_variant_id=payload.resume_variant_id,
        template_id=payload.template_id,
        step_number=payload.step_number,
        job_opening_id=payload.job_opening_id,
        steering_note=payload.steering_note,
    )
    return await generate_email(ctx)
