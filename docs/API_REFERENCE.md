# Farmland Processing Pipeline — API Reference

**Version:** 2.0.0  
**Base URL:** `http://localhost:8000`  
**Interactive Docs:** `http://localhost:8000/docs` (Swagger UI)

---

## Overview

The Farmland Processing Pipeline is a FastAPI microservice that loads raw farmland coordinate data from an Excel source, applies **Silent Healing** auto-fixes, processes the geometry through Shapely, and returns a strict **RFC 7946-compliant GeoJSON Feature**. Every auto-fix applied is recorded in a `fixes_applied` telemetry array inside the response `properties`.

---

## Authentication

None required. This is an internal developer/tooling API.

---

## Common Response Structure

All successful geometry responses follow the **RFC 7946 GeoJSON Feature** format. All custom metadata is enclosed strictly within `properties` — no custom fields appear at the Feature root level.

```json
{
  "type": "Feature",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[lon, lat], ...]],
    "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
  },
  "properties": {
    "status": "success | success_with_fixes",
    "kvk_number": "9011743132",
    "fixes_applied": ["..."],
    "error_message": null,
    "crs": "EPSG:4326"
  }
}
```

---

## Endpoints

---

### `GET /api/farm/{phone_number}`

Retrieves, cleans, and returns the processed GeoJSON polygon for a given farmer identified by their phone number.

#### Path Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `phone_number` | `string` | ✅ | The farmer's registered phone number (KVK number). |

#### Silent Healing Telemetry

The pipeline applies the following auto-fixes silently and records each action in `properties.fixes_applied`:

| Fix | Trigger Condition | Telemetry Message |
|---|---|---|
| Space removal | A coordinate cell contains whitespace | `"Removed accidental spaces from coordinates."` |
| Decimal injection | A coordinate segment has no `.` character | `"Injected missing decimal point."` |
| Convex Hull repair | Shapely reports `geom.is_valid == False` | `"Applied Convex Hull to repair self-intersecting polygon."` |

If no fixes were needed, `properties.fixes_applied` will be an empty array `[]` and `properties.status` will be `"success"`.

#### Status Values

| Status | Meaning |
|---|---|
| `success` | Data was clean; no fixes were applied. |
| `success_with_fixes` | One or more auto-fixes were applied. |

#### Success Response — `200 OK`

```json
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
    ],
    "crs": {
      "type": "name",
      "properties": { "name": "EPSG:4326" }
    }
  },
  "properties": {
    "status": "success_with_fixes",
    "kvk_number": "9011743132",
    "fixes_applied": [
      "Injected missing decimal point.",
      "Removed accidental spaces from coordinates."
    ],
    "error_message": null,
    "crs": "EPSG:4326"
  }
}
```

#### Error Responses

| HTTP Code | When | `detail` Example |
|---|---|---|
| `404 Not Found` | Phone number not found in database | `"No farmland record found for phone number: 1234567890"` |
| `503 Service Unavailable` | `farmers_data.xls` file is missing | `"Data source unavailable. The farmers_data.xls file is missing."` |
| `500 Internal Server Error` | Unexpected processing failure | `"Internal error while processing farm data: ..."` |

All error responses follow FastAPI's standard format:
```json
{ "detail": "<error description>" }
```

---

### `POST /api/sentinel/submit`

Accepts a processed GeoJSON Feature payload and simulates a handoff to the Remote Sensing (Sentinel-2) satellite imagery pipeline.

> **Note:** This endpoint is currently mocked. In production, it would forward the payload to an external satellite API.

#### Request Body

```json
{
  "geojson_payload": {
    "type": "Feature",
    "geometry": { "..." : "..." },
    "properties": { "..." : "..." }
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `geojson_payload` | `object` | ✅ | The full GeoJSON Feature object returned by `GET /api/farm/{phone_number}`. |

#### Success Response — `200 OK`

```json
{
  "status": "success",
  "message": "Simulated handoff to Remote Sensing API successful."
}
```

---

### `POST /api/process_farm` *(Deprecated)*

> ⚠️ **Deprecated.** This legacy endpoint is maintained for backward compatibility only. Use `GET /api/farm/{phone_number}` instead.

Accepts a JSON body `{ "phone_number": "..." }` and returns the same GeoJSON Feature response as the GET endpoint.

---

## Running the Service

```bash
# From the project root
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

| URL | Purpose |
|---|---|
| `http://localhost:8000` | Developer Testing Dashboard |
| `http://localhost:8000/docs` | Swagger UI (interactive docs) |
| `http://localhost:8000/redoc` | ReDoc documentation |
