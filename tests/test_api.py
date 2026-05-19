"""
Tests for the Farmland Processing Pipeline API.

These are integration tests that require a running PostGIS database
with populated data. Run `docker compose up -d` before testing.
"""

import pytest
from httpx import AsyncClient


# ── Health Check ──────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_health_check(client: AsyncClient):
    """GET /health should return 200 with a status field."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert data["version"] == "4.0.0"


@pytest.mark.anyio
async def test_health_check_database_connected(client: AsyncClient):
    """Health check should report database as connected."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


# ── Root / Dashboard ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_root_serves_dashboard(client: AsyncClient):
    """GET / should return 200 and serve the HTML dashboard."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# ── GeoJSON Endpoint — All Farms ──────────────────────────────────────────────

@pytest.mark.anyio
async def test_geojson_returns_feature_collection(client: AsyncClient):
    """GET /api/farms/geojson should return a valid GeoJSON FeatureCollection."""
    response = await client.get("/api/farms/geojson")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert isinstance(data["features"], list)


@pytest.mark.anyio
async def test_geojson_features_have_correct_structure(client: AsyncClient):
    """Each Feature should have type, geometry, and properties with farm_id."""
    response = await client.get("/api/farms/geojson")
    assert response.status_code == 200
    data = response.json()
    for feature in data["features"]:
        assert feature["type"] == "Feature"
        assert "geometry" in feature
        assert "type" in feature["geometry"]
        assert "coordinates" in feature["geometry"]
        assert "properties" in feature
        assert "farm_id" in feature["properties"]


@pytest.mark.anyio
async def test_geojson_geometry_types_are_valid(client: AsyncClient):
    """Geometry types should be either Polygon or MultiPolygon."""
    response = await client.get("/api/farms/geojson")
    assert response.status_code == 200
    data = response.json()
    valid_types = {"Polygon", "MultiPolygon"}
    for feature in data["features"]:
        assert feature["geometry"]["type"] in valid_types


# ── GeoJSON Endpoint — Filtering by farm_id ───────────────────────────────────

@pytest.mark.anyio
async def test_geojson_filter_by_farm_id(client: AsyncClient):
    """GET /api/farms/geojson?farm_id=X should return only that farm."""
    response = await client.get("/api/farms/geojson?farm_id=8805508334")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1
    assert data["features"][0]["properties"]["farm_id"] == "8805508334"


@pytest.mark.anyio
async def test_geojson_filter_nonexistent_farm_id(client: AsyncClient):
    """Filtering by a non-existent farm_id should return an empty FeatureCollection."""
    response = await client.get("/api/farms/geojson?farm_id=0000000000")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 0


# ── GeoJSON Endpoint — Pagination ─────────────────────────────────────────────

@pytest.mark.anyio
async def test_geojson_pagination_limit(client: AsyncClient):
    """Limit parameter should cap the number of returned features."""
    response = await client.get("/api/farms/geojson?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["features"]) <= 2


@pytest.mark.anyio
async def test_geojson_pagination_offset(client: AsyncClient):
    """Offset should skip features — offset beyond total should return empty."""
    response = await client.get("/api/farms/geojson?limit=100&offset=9999")
    assert response.status_code == 200
    data = response.json()
    assert len(data["features"]) == 0


@pytest.mark.anyio
async def test_geojson_pagination_invalid_limit(client: AsyncClient):
    """Invalid limit (< 1 or > 1000) should return 422 validation error."""
    response = await client.get("/api/farms/geojson?limit=0")
    assert response.status_code == 422

    response = await client.get("/api/farms/geojson?limit=9999")
    assert response.status_code == 422


@pytest.mark.anyio
async def test_geojson_pagination_invalid_offset(client: AsyncClient):
    """Negative offset should return 422 validation error."""
    response = await client.get("/api/farms/geojson?offset=-1")
    assert response.status_code == 422


# ── Swagger Docs ──────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_swagger_docs_available(client: AsyncClient):
    """GET /docs should return 200 (Swagger UI)."""
    response = await client.get("/docs")
    assert response.status_code == 200
