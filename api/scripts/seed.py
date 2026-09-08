"""Seed the database with the single admin user from env.

Usage: python -m scripts.seed
"""
import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models import AdminUser


async def seed_admin_user() -> None:
    settings = get_settings()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AdminUser).where(AdminUser.email == settings.admin_email)
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            print(f"Admin user already exists: {existing.email}")
            return

        admin = AdminUser(
            email=settings.admin_email,
            hashed_password=hash_password(settings.admin_password),
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        print(f"Created admin user: {admin.email}")


async def main() -> None:
    await seed_admin_user()


if __name__ == "__main__":
    asyncio.run(main())
