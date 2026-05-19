# Farmland Processing Pipeline — API Reference

**Version:** 4.0.0  
**Base URL:** `http://localhost:8000`  
**Interactive Docs:** `http://localhost:8000/docs` (Swagger UI)

---

## Overview

The Farmland Processing Pipeline is a high-performance FastAPI microservice that queries pre-calculated GIS data from a **PostGIS Materialized View** and serves it as a strict **RFC 7946-compliant GeoJSON FeatureCollection**. By offloading all spatial coordinate math and data normalization to the database layer, the API achieves high-throughput performance capable of scaling to large volumes of records.

---

## Authentication

None required. This is an internal developer/tooling API.

---

## Response Structure

The successful geometry response follows the **RFC 7946 GeoJSON FeatureCollection** format. Custom metadata (such as the farmer ID) is enclosed strictly within `properties` for each `Feature`.

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[lon, lat], ...]]
      },
      "properties": {
        "farm_id": "9011743132"
      }
    }
  ]
}
```

---

## Endpoints

---

### `GET /health`

Returns the health status of the API and its database connection.

#### Success Response — `200 OK`

```json
{
  "status": "healthy",
  "database": "connected",
  "version": "4.0.0"
}
```

---

### `GET /api/farms/geojson`

Retrieves processed farmland geometries as a unified `FeatureCollection`.

#### Query Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `farm_id` | `string` | `null` | Optional. Filter by a specific farm ID (phone number). |
| `limit` | `integer` | `100` | Max features per page (1–1000). Ignored when `farm_id` is set. |
| `offset` | `integer` | `0` | Number of features to skip. Ignored when `farm_id` is set. |

#### Performance
This endpoint directly queries the `processed_farm_geojson` materialized view and returns the pre-formatted `geojson` strings, avoiding any heavy Python spatial transformations.

#### Example — Fetch a specific farm
```bash
curl http://localhost:8000/api/farms/geojson?farm_id=8805508334
```

#### Example — Paginated fetch
```bash
curl "http://localhost:8000/api/farms/geojson?limit=10&offset=0"
```

#### Success Response — `200 OK`

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [78.456123, 17.234567],
            [78.461234, 17.238901],
            [78.458765, 17.241234],
            [78.456123, 17.234567]
          ]
        ]
      },
      "properties": {
        "farm_id": "9011743132"
      }
    }
  ]
}
```

#### Error Responses

| HTTP Code | When | `detail` Example |
|---|---|---|
| `422 Unprocessable Entity` | Invalid query parameters (e.g., limit=0) | `"Input should be greater than or equal to 1"` |
| `500 Internal Server Error` | Database connection failure or query error | `"Could not retrieve processed farm GeoJSON."` |

All error responses follow FastAPI's standard format:
```json
{ "detail": "<error description>" }
```

---

## Running the Service

```bash
# From the project root
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

| URL | Purpose |
|---|---|
| `http://localhost:8000` | Developer Testing Dashboard |
| `http://localhost:8000/health` | Health Check Endpoint |
| `http://localhost:8000/docs` | Swagger UI (interactive docs) |
| `http://localhost:8000/redoc` | ReDoc documentation |
