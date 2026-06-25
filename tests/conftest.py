"""
Pytest configuration for async integration tests.

Uses a NullPool engine to avoid asyncpg event loop conflicts in testing.
Each test gets a fresh connection from the pool, with no cross-loop issues.
"""

import os
import pytest

# Set test environment variables
os.environ["API_KEY"] = "test-api-key"
os.environ["ALLOWED_ORIGINS"] = "http://testserver"

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from httpx import AsyncClient, ASGITransport

from src.services.database import DATABASE_URL, get_db_session
from src.main import app


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use the default event loop policy."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(scope="session")
async def test_engine():
    """
    Create a fresh async engine with NullPool for testing.
    NullPool creates a new connection for each request and closes it immediately,
    avoiding all event-loop-binding issues with asyncpg's connection pool.
    """
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        poolclass=NullPool,
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def test_session_factory(test_engine):
    """Session factory bound to the test engine."""
    return async_sessionmaker(
        test_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )


@pytest.fixture(autouse=True)
async def override_db(test_session_factory):
    """
    Override the FastAPI DB dependency so the app uses the test engine
    (NullPool, bound to the test event loop).
    """
    async def _test_get_db_session():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _test_get_db_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client():
    """Async HTTP test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
