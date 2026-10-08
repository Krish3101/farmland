"""Pytest configuration: tests run against the PostGIS database in DATABASE_URL."""

import os
import socket
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from src.main import DATABASE_URL, SessionLocal, app


def _is_db_reachable() -> bool:
    try:
        url = urlparse(DATABASE_URL)
        with socket.create_connection((url.hostname, url.port or 5432), timeout=0.3):
            return True
    except (OSError, ValueError):
        return False


is_db_reachable = _is_db_reachable()

if os.getenv("REQUIRE_DB") and not is_db_reachable:
    raise pytest.UsageError("REQUIRE_DB is set but the database in DATABASE_URL is unreachable.")

requires_db = pytest.mark.skipif(
    not is_db_reachable,
    reason="no PostGIS at DATABASE_URL (start the container from the README)",
)


@pytest.fixture
def db():
    """A database session for tests that query the views directly."""
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    """HTTP test client for the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client
