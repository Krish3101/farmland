"""
Tests for the Farmland API.

These are integration tests that require a running PostGIS database
with populated data. Run `docker compose up -d` before testing.
"""

from httpx import AsyncClient

from tests.conftest import requires_db

AUTH = {"X-API-Key": "test-api-key"}

# Health check


@requires_db
async def test_health_check(client: AsyncClient):
    """GET /health should return 200 with a status field."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert data["version"] == "0.1.0"


@requires_db
async def test_health_check_database_connected(client: AsyncClient):
    """Health check should report database as connected."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


async def test_health_check_database_disconnected(client: AsyncClient):
    """Health check should return 503 when database is unreachable."""
    from src.main import app
    from src.services.database import get_db_session

    saved_override = app.dependency_overrides.get(get_db_session)

    async def _failing_db_session():
        class MockFailingSession:
            async def execute(self, *args, **kwargs):
                raise ConnectionRefusedError("Database connection refused")

        yield MockFailingSession()

    app.dependency_overrides[get_db_session] = _failing_db_session
    try:
        response = await client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        # The driver error is logged, not returned to the caller.
        assert data["error"] == "Database connectivity check failed."
    finally:
        if saved_override:
            app.dependency_overrides[get_db_session] = saved_override
        else:
            app.dependency_overrides.pop(get_db_session, None)


# Root / dashboard


async def test_root_serves_dashboard(client: AsyncClient):
    """GET / should return 200 and serve the HTML dashboard."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# Authentication


async def test_geojson_unauthorized_missing_key(client: AsyncClient):
    """GET /api/farms/geojson without X-API-Key should return 401 Unauthorized."""
    response = await client.get("/api/farms/geojson")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API Key."


async def test_geojson_unauthorized_invalid_key(client: AsyncClient):
    """GET /api/farms/geojson with incorrect X-API-Key should return 401 Unauthorized."""
    response = await client.get("/api/farms/geojson", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API Key."


async def test_geojson_server_unconfigured_key(client: AsyncClient, monkeypatch):
    """Protected endpoints return 500 when API_KEY is not configured on server."""
    monkeypatch.delenv("API_KEY", raising=False)
    response = await client.get("/api/farms/geojson", headers=AUTH)
    assert response.status_code == 500
    assert response.json()["detail"] == "API Key configuration error on server."


# GeoJSON endpoint: all farms


@requires_db
async def test_geojson_returns_feature_collection(client: AsyncClient):
    """GET /api/farms/geojson should return a valid GeoJSON FeatureCollection."""
    response = await client.get("/api/farms/geojson", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert isinstance(data["features"], list)


@requires_db
async def test_geojson_features_have_correct_structure(client: AsyncClient):
    """Each Feature should have type, geometry, and properties with farm_id."""
    response = await client.get("/api/farms/geojson", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    for feature in data["features"]:
        assert feature["type"] == "Feature"
        assert "geometry" in feature
        assert "type" in feature["geometry"]
        assert "coordinates" in feature["geometry"]
        assert "properties" in feature
        assert "farm_id" in feature["properties"]


@requires_db
async def test_geojson_geometry_types_are_valid(client: AsyncClient):
    """Geometry types should be either Polygon or MultiPolygon."""
    response = await client.get("/api/farms/geojson", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    valid_types = {"Polygon", "MultiPolygon"}
    for feature in data["features"]:
        assert feature["geometry"]["type"] in valid_types


# GeoJSON endpoint: filtering by farm_id


@requires_db
async def test_geojson_filter_by_farm_id(client: AsyncClient):
    """GET /api/farms/geojson?farm_id=X should return only that farm."""
    response = await client.get("/api/farms/geojson?farm_id=8805508334", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1
    assert data["features"][0]["properties"]["farm_id"] == "8805508334"


@requires_db
async def test_geojson_filter_nonexistent_farm_id(client: AsyncClient):
    """Filtering by a non-existent farm_id should return an empty FeatureCollection."""
    response = await client.get("/api/farms/geojson?farm_id=0000000000", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 0


# GeoJSON endpoint: pagination


@requires_db
async def test_geojson_pagination_limit(client: AsyncClient):
    """Limit parameter should cap the number of returned features."""
    response = await client.get("/api/farms/geojson?limit=2", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert len(data["features"]) <= 2


@requires_db
async def test_geojson_pagination_offset(client: AsyncClient):
    """Offset should skip features; offset beyond total should return empty."""
    response = await client.get("/api/farms/geojson?limit=100&offset=9999", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert len(data["features"]) == 0


async def test_geojson_pagination_invalid_limit(client: AsyncClient):
    """Invalid limit (< 1 or > 1000) should return 422 validation error."""
    response = await client.get("/api/farms/geojson?limit=0", headers=AUTH)
    assert response.status_code == 422

    response = await client.get("/api/farms/geojson?limit=9999", headers=AUTH)
    assert response.status_code == 422


async def test_geojson_pagination_invalid_offset(client: AsyncClient):
    """Negative offset should return 422 validation error."""
    response = await client.get("/api/farms/geojson?offset=-1", headers=AUTH)
    assert response.status_code == 422


# Swagger docs


async def test_swagger_docs_available(client: AsyncClient):
    """GET /docs should return 200 (Swagger UI)."""
    response = await client.get("/docs")
    assert response.status_code == 200
