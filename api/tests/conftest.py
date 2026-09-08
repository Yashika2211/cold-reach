import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.db import session as db_session_module
from app.main import app

settings = get_settings()
TEST_DATABASE_URL = settings.database_url.rsplit("/", 1)[0] + "/coldreach_test"


@pytest_asyncio.fixture
async def engine():
    test_engine = create_async_engine(TEST_DATABASE_URL)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    connection = await engine.connect()
    transaction = await connection.begin()
    session_maker = async_sessionmaker(bind=connection, expire_on_commit=False)
    session = session_maker()

    async def override_get_db():
        yield session

    app.dependency_overrides[db_session_module.get_db] = override_get_db

    yield session

    await session.close()
    await transaction.rollback()
    await connection.close()
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
