from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.redis import get_redis
from app.core.security import hash_password
from app.db import session as db_session_module
from app.db.base import Base
from app.main import app
from app.models import AdminUser, SendingAccount
from app.models.enums import SendingAccountProvider
from app.services.sending_accounts import encrypt_credentials

settings = get_settings()
TEST_DATABASE_URL = settings.database_url.rsplit("/", 1)[0] + "/coldreach_test"
# A dedicated Redis logical DB so test runs never collide with dev-server state.
TEST_REDIS_URL = settings.redis_url.rsplit("/", 1)[0] + "/15"


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
async def db_connection(engine):
    """Exposed separately from db_session so tests can bind a second, independent
    Session (e.g. one standing in for a Celery task's own AsyncSessionLocal) to the
    exact same connection/transaction — both then join the same external transaction
    and roll back together at teardown."""
    connection = await engine.connect()
    transaction = await connection.begin()
    yield connection
    await transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture
async def db_session(db_connection) -> AsyncGenerator[AsyncSession, None]:
    session_maker = async_sessionmaker(bind=db_connection, expire_on_commit=False)
    session = session_maker()

    async def override_get_db():
        yield session

    app.dependency_overrides[db_session_module.get_db] = override_get_db

    yield session

    await session.close()
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[Redis, None]:
    test_redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await test_redis.flushdb()

    async def override_get_redis():
        return test_redis

    app.dependency_overrides[get_redis] = override_get_redis

    yield test_redis

    await test_redis.flushdb()
    await test_redis.aclose()


@pytest_asyncio.fixture
async def client(db_session, redis_client) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "test-password-123"


@pytest_asyncio.fixture
async def admin_user(db_session) -> AdminUser:
    admin = AdminUser(email=ADMIN_EMAIL, hashed_password=hash_password(ADMIN_PASSWORD), is_active=True)
    db_session.add(admin)
    await db_session.flush()
    return admin


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient, admin_user: AdminUser) -> AsyncClient:
    response = await client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return client


@pytest_asyncio.fixture
async def smtp_sending_account(db_session) -> SendingAccount:
    account = SendingAccount(
        display_name="Test SMTP Account",
        from_address="tester@example.com",
        provider_type=SendingAccountProvider.smtp,
        daily_cap=40,
        encrypted_credentials=encrypt_credentials(
            {
                "host": "smtp.example.com",
                "port": 587,
                "username": "tester@example.com",
                "password": "app-password",
                "use_starttls": True,
            }
        ),
        health_metrics={},
        is_active=True,
    )
    db_session.add(account)
    await db_session.flush()
    return account
