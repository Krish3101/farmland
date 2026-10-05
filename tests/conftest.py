"""
Pytest configuration for the async integration tests.

The test engine uses NullPool, so a connection is opened and closed per use.
Pooled asyncpg connections stay bound to the event loop that created them,
which breaks when they are reused across tests.
"""

import os
import socket
from urllib.parse import urlparse

import pytest
from dotenv import load_dotenv

# Must run before src.main is imported below. Values already in the environment win.
load_dotenv()
# The tests send this key, so it overrides whatever .env or CI sets.
os.environ["API_KEY"] = "test-api-key"

if not os.getenv("DATABASE_URL"):
    if os.getenv("REQUIRE_DB"):
        raise pytest.UsageError("REQUIRE_DB is set but DATABASE_URL is not.")
    # Nothing listens on port 1, so the DB tests skip instead of guessing a real database.
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://unset@127.0.0.1:1/unset"

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.db import DATABASE_URL, get_db_session
from src.main import app


def _is_db_reachable() -> bool:
    try:
        url = urlparse(DATABASE_URL.replace("+asyncpg", ""))
        host = url.hostname or "127.0.0.1"
        port = url.port or 5432
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except (OSError, ValueError):
        return False


is_db_reachable = _is_db_reachable()

if os.getenv("REQUIRE_DB") and not is_db_reachable:
    raise pytest.UsageError("REQUIRE_DB is set but the database in DATABASE_URL is unreachable.")

requires_db = pytest.mark.skipif(
    not is_db_reachable,
    reason="no PostGIS at DATABASE_URL (run ./scripts/start.sh, or set it in .env)",
)


@pytest.fixture(scope="session")
async def test_engine():
    """Async engine for tests, unpooled to avoid event-loop binding."""
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
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
    # ASGITransport skips the lifespan, so run it here to load the API key.
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac
