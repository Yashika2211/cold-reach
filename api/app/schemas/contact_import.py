from typing import Literal

from pydantic import BaseModel

ImportField = Literal[
    "first_name", "last_name", "email", "title", "company_name", "linkedin_url", "notes"
]

ColumnMapping = dict[ImportField, str | None]


class ImportParseResponse(BaseModel):
    import_token: str
    headers: list[str]
    sample_rows: list[dict[str, str | None]]
    suggested_mapping: ColumnMapping
    row_count: int


class ImportRequest(BaseModel):
    import_token: str
    mapping: ColumnMapping


class RowResult(BaseModel):
    row_number: int
    action: Literal["create", "skip_duplicate", "error"]
    data: dict[str, str | None]
    error: str | None = None


class ImportSummary(BaseModel):
    create: int
    skip_duplicate: int
    error: int


class ImportPreviewResponse(BaseModel):
    results: list[RowResult]
    summary: ImportSummary


class ImportCommitResponse(BaseModel):
    created: int
    skipped_duplicate: int
    skipped_invalid: int
    errors: list[RowResult]
