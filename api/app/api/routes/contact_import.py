from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.redis import get_redis
from app.db.session import get_db
from app.schemas.contact_import import (
    ImportCommitResponse,
    ImportParseResponse,
    ImportPreviewResponse,
    ImportRequest,
    ImportSummary,
)
from app.services.contact_import import (
    MAX_CSV_BYTES,
    SAMPLE_ROW_COUNT,
    cache_import,
    discard_cached_import,
    load_cached_import,
    parse_csv_text,
    process_rows,
    suggest_mapping,
)

router = APIRouter(
    prefix="/contacts/import", tags=["contacts"], dependencies=[Depends(get_current_admin)]
)


async def _finish_parse(raw_text: str, redis: Redis) -> ImportParseResponse:
    headers, rows = parse_csv_text(raw_text)
    token = await cache_import(redis, headers, rows)

    return ImportParseResponse(
        import_token=token,
        headers=headers,
        sample_rows=rows[:SAMPLE_ROW_COUNT],
        suggested_mapping=suggest_mapping(headers),
        row_count=len(rows),
    )


@router.post("/parse-file", response_model=ImportParseResponse)
async def parse_file(file: UploadFile, redis: Redis = Depends(get_redis)):
    contents = await file.read(MAX_CSV_BYTES + 1)
    if len(contents) > MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds the {MAX_CSV_BYTES // (1024 * 1024)}MB limit",
        )
    return await _finish_parse(contents.decode("utf-8-sig", errors="replace"), redis)


class ParseTextRequest(BaseModel):
    text: str


@router.post("/parse-text", response_model=ImportParseResponse)
async def parse_text(payload: ParseTextRequest, redis: Redis = Depends(get_redis)):
    if len(payload.text.encode()) > MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pasted text exceeds the {MAX_CSV_BYTES // (1024 * 1024)}MB limit",
        )
    return await _finish_parse(payload.text, redis)


@router.post("/preview", response_model=ImportPreviewResponse)
async def preview_import(
    payload: ImportRequest, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)
):
    _headers, rows = await load_cached_import(redis, payload.import_token)
    results = await process_rows(db, rows, payload.mapping, commit=False)

    summary = ImportSummary(
        create=sum(1 for r in results if r.action == "create"),
        skip_duplicate=sum(1 for r in results if r.action == "skip_duplicate"),
        error=sum(1 for r in results if r.action == "error"),
    )
    return ImportPreviewResponse(results=results, summary=summary)


@router.post("/commit", response_model=ImportCommitResponse)
async def commit_import(
    payload: ImportRequest, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)
):
    _headers, rows = await load_cached_import(redis, payload.import_token)
    results = await process_rows(db, rows, payload.mapping, commit=True)
    await db.commit()
    await discard_cached_import(redis, payload.import_token)

    return ImportCommitResponse(
        created=sum(1 for r in results if r.action == "create"),
        skipped_duplicate=sum(1 for r in results if r.action == "skip_duplicate"),
        skipped_invalid=sum(1 for r in results if r.action == "error"),
        errors=[r for r in results if r.action == "error"],
    )
