import csv
import io
import uuid
from json import dumps, loads

from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, Contact
from app.models.enums import ContactSource
from app.schemas.contact_import import ColumnMapping, ImportField, RowResult
from app.services.email_utils import normalize_email

MAX_CSV_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_CSV_ROWS = 2000
IMPORT_CACHE_TTL_SECONDS = 30 * 60
SAMPLE_ROW_COUNT = 5

FIELD_ALIASES: dict[ImportField, list[str]] = {
    "first_name": ["first name", "firstname", "first", "given name"],
    "last_name": ["last name", "lastname", "last", "surname", "family name"],
    "email": ["email", "email address", "e-mail", "emailaddress"],
    "title": ["title", "job title", "position", "role"],
    "company_name": ["company", "company name", "organization", "organisation", "employer"],
    "linkedin_url": ["linkedin", "linkedin url", "linkedin profile", "linkedin link"],
    "notes": ["notes", "note", "comment", "comments"],
}


def _normalize_header(header: str) -> str:
    return header.strip().lower().replace("_", " ")


def suggest_mapping(headers: list[str]) -> ColumnMapping:
    normalized_headers = {h: _normalize_header(h) for h in headers}
    mapping: ColumnMapping = {}

    for field, aliases in FIELD_ALIASES.items():
        match: str | None = None
        for header, normalized in normalized_headers.items():
            if normalized in aliases or normalized == field.replace("_", " "):
                match = header
                break
        mapping[field] = match

    return mapping


def parse_csv_text(raw_text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(raw_text))
    headers = reader.fieldnames or []
    if not headers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No columns found in CSV")

    rows: list[dict[str, str]] = []
    for row in reader:
        # DictReader puts overflow columns under the None key; drop them, and coerce
        # missing/short-row values (None) to empty strings for consistent downstream handling.
        rows.append({k: (v or "") for k, v in row.items() if k is not None})
        if len(rows) > MAX_CSV_ROWS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CSV has more than {MAX_CSV_ROWS} rows. Split it into smaller files.",
            )

    return headers, rows


async def cache_import(redis: Redis, headers: list[str], rows: list[dict[str, str]]) -> str:
    token = str(uuid.uuid4())
    payload = dumps({"headers": headers, "rows": rows})
    await redis.set(f"import:{token}", payload, ex=IMPORT_CACHE_TTL_SECONDS)
    return token


async def load_cached_import(redis: Redis, token: str) -> tuple[list[str], list[dict[str, str]]]:
    raw = await redis.get(f"import:{token}")
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import session expired or not found. Please re-upload.",
        )
    payload = loads(raw)
    return payload["headers"], payload["rows"]


async def discard_cached_import(redis: Redis, token: str) -> None:
    await redis.delete(f"import:{token}")


def _extract_mapped(row: dict[str, str], mapping: ColumnMapping) -> dict[str, str | None]:
    extracted: dict[str, str | None] = {}
    for field, column in mapping.items():
        if column is None:
            extracted[field] = None
        else:
            value = row.get(column, "")
            extracted[field] = value.strip() if value else None
    return extracted


async def process_rows(
    db: AsyncSession,
    rows: list[dict[str, str]],
    mapping: ColumnMapping,
    commit: bool,
) -> list[RowResult]:
    """Validate (and optionally write) every row. Shared by the preview and commit endpoints
    so their dedupe/error logic can never drift apart."""

    extracted_rows = [_extract_mapped(row, mapping) for row in rows]

    candidate_normalized_emails = {
        normalize_email(data["email"]) for data in extracted_rows if data.get("email")
    }
    existing_normalized_emails: set[str] = set()
    if candidate_normalized_emails:
        existing_result = await db.execute(
            select(Contact.normalized_email).where(
                Contact.deleted_at.is_(None),
                Contact.normalized_email.in_(candidate_normalized_emails),
            )
        )
        existing_normalized_emails = set(existing_result.scalars().all())

    company_cache: dict[str, Company] = {}
    if commit:
        company_names = {
            data["company_name"].strip()
            for data in extracted_rows
            if data.get("company_name")
        }
        if company_names:
            existing_companies = await db.execute(
                select(Company).where(Company.deleted_at.is_(None))
            )
            for company in existing_companies.scalars().all():
                company_cache[company.name.strip().lower()] = company

    seen_in_batch: set[str] = set()
    results: list[RowResult] = []

    for index, data in enumerate(extracted_rows, start=1):
        email = data.get("email")

        if not email:
            results.append(RowResult(row_number=index, action="error", data=data, error="Missing email"))
            continue

        try:
            validated = validate_email(email, check_deliverability=False)
        except EmailNotValidError as exc:
            results.append(RowResult(row_number=index, action="error", data=data, error=str(exc)))
            continue

        normalized = normalize_email(validated.normalized)

        if normalized in existing_normalized_emails or normalized in seen_in_batch:
            results.append(RowResult(row_number=index, action="skip_duplicate", data=data, error=None))
            continue

        seen_in_batch.add(normalized)
        results.append(RowResult(row_number=index, action="create", data=data, error=None))

        if commit:
            company = None
            company_name = data.get("company_name")
            if company_name:
                key = company_name.strip().lower()
                company = company_cache.get(key)
                if company is None:
                    company = Company(name=company_name.strip())
                    db.add(company)
                    await db.flush()
                    company_cache[key] = company

            contact = Contact(
                first_name=data.get("first_name"),
                last_name=data.get("last_name"),
                email=validated.normalized,
                normalized_email=normalized,
                title=data.get("title"),
                company_id=company.id if company else None,
                linkedin_url=data.get("linkedin_url"),
                notes=data.get("notes"),
                source=ContactSource.csv,
            )
            db.add(contact)

    return results
