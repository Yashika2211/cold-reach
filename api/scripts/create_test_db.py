"""Create the coldreach_test database if it doesn't exist yet. Run before pytest."""
import asyncio

import asyncpg

from app.core.config import get_settings


async def main() -> None:
    settings = get_settings()
    # asyncpg needs a plain postgresql:// DSN, not the +asyncpg SQLAlchemy variant.
    admin_dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://").rsplit(
        "/", 1
    )[0] + "/postgres"
    test_db_name = "coldreach_test"

    conn = await asyncpg.connect(admin_dsn)
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", test_db_name
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{test_db_name}"')
            print(f"Created database {test_db_name}")
        else:
            print(f"Database {test_db_name} already exists")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
