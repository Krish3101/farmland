"""The four endpoints, against the PostGIS database with the sheet loaded by ingest.py."""

from fastapi.testclient import TestClient

from tests.conftest import requires_db


@requires_db
def test_list_farms_returns_ten_polygons(client: TestClient):
    response = client.get("/api/farms")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 10
    assert {f["geometry"]["type"] for f in data["features"]} == {"Polygon"}


@requires_db
def test_get_one_farm(client: TestClient):
    response = client.get("/api/farms/8805508334")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "Feature"
    assert data["properties"] == {"farm_id": "8805508334", "area_m2": 4580.5}


@requires_db
def test_unknown_farm_is_404(client: TestClient):
    assert client.get("/api/farms/0000000000").status_code == 404


@requires_db
def test_rejections_empty_for_the_clean_sheet(client: TestClient):
    response = client.get("/api/rejections")
    assert response.status_code == 200
    assert response.json() == []


@requires_db
def test_health_endpoint(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


@requires_db
def test_list_farms_pagination(client: TestClient):
    response = client.get("/api/farms?limit=3&offset=2")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 3
