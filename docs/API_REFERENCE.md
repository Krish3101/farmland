# API reference

Base URL `http://localhost:8000`. FastAPI serves its own interactive docs at `/docs`
and `/redoc`, which are generated from the code and so can't drift from it — this file
covers the parts those pages don't explain.

Every `/api` route requires an `X-API-Key` header matching the server's `API_KEY`.
A missing or wrong key is a 401; if the server itself has no `API_KEY` configured,
requests fail with a 500 rather than being let through.

## GET /health

Unauthenticated. Returns 200 when the database answers, 503 when it doesn't.

```json
{ "status": "healthy", "database": "connected", "version": "0.1.0" }
```

The 503 body has the same shape with `"status": "unhealthy"`, `"database": "disconnected"`
and an `error` field.

## GET /api/farms/geojson

Returns farm boundaries as an RFC 7946 `FeatureCollection`. The farmer id travels in each
feature's `properties`, since RFC 7946 has nowhere else to put application data.

| Parameter | Type | Default | |
|---|---|---|---|
| `farm_id` | string | — | Filter to one farm, by phone number. Makes `limit` and `offset` irrelevant. |
| `limit` | integer | 100 | Features per page, 1–1000. |
| `offset` | integer | 0 | Features to skip. |

```bash
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/farms/geojson?farm_id=9000000001"

curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/farms/geojson?limit=10&offset=0"
```

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
      "properties": { "farm_id": "9011743132" }
    }
  ]
}
```

The response comes straight out of the `processed_farm_geojson` materialized view. The
coordinate cleaning and spatial work all happened at refresh time, so a read is an indexed
lookup and does no geometry work in Python.

Errors use FastAPI's `{"detail": "..."}` shape: 422 for a bad parameter (`limit=0` gives
"Input should be greater than or equal to 1"), 401 for a bad key, 500 if the view can't be
read.
