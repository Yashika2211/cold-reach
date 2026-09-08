from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SuppressionEntry
from app.models.enums import SuppressionReason, SuppressionSource
from app.services.email_utils import normalize_email


async def is_suppressed(db: AsyncSession, email: str) -> bool:
    normalized = normalize_email(email)
    result = await db.execute(
        select(SuppressionEntry.id).where(SuppressionEntry.normalized_email == normalized)
    )
    return result.scalar_one_or_none() is not None


async def get_suppressed_set(db: AsyncSession, emails: list[str]) -> set[str]:
    """Bulk-check which of the given emails (any casing) are suppressed. Returns normalized emails."""
    normalized = {normalize_email(e) for e in emails}
    if not normalized:
        return set()
    result = await db.execute(
        select(SuppressionEntry.normalized_email).where(
            SuppressionEntry.normalized_email.in_(normalized)
        )
    )
    return set(result.scalars().all())


async def add_suppression(
    db: AsyncSession,
    email: str,
    reason: SuppressionReason,
    source: SuppressionSource,
) -> SuppressionEntry:
    normalized = normalize_email(email)
    result = await db.execute(
        select(SuppressionEntry).where(SuppressionEntry.normalized_email == normalized)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    entry = SuppressionEntry(
        email=email.strip(), normalized_email=normalized, reason=reason, source=source
    )
    db.add(entry)
    await db.flush()
    return entry
