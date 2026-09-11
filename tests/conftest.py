"""
Pytest configuration for the async integration tests.

The test engine uses NullPool, so a connection is opened and closed per use.
Pooled asyncpg connections stay bound to the event loop that created them,
which breaks when they are reused across tests.
"""

import os

import pytest

# Must be set before src.main is imported below.
os.environ["API_KEY"] = "test-api-key"
os.environ["ALLOWED_ORIGINS"] = "http://testserver"

import socket
from urllib.parse import urlparse

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.main import app
from src.services.database import DATABASE_URL, get_db_session


def _is_db_reachable() -> bool:
    try:
        url = urlparse(DATABASE_URL.replace("+asyncpg", ""))
        host = url.hostname or "127.0.0.1"
        port = url.port or 5434
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except Exception:
        return False


is_db_reachable = _is_db_reachable()
requires_db = pytest.mark.skipif(
    not is_db_reachable,
    reason="PostGIS database container not running (run 'docker compose up -d')",
)


@pytest.fixture(scope="session")
async def test_engine():
    """Async engine for tests, unpooled to avoid event-loop binding."""
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
