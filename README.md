# Farmland

Farm boundaries arrive in a spreadsheet as four GPS corners typed by hand, with stray spaces, missing decimal points, swapped latitude and longitude, and degree signs. Farmland repairs those strings inside PostGIS into valid farm polygons with an area, serves them as GeoJSON, and lists every farm it could not repair with the reason, so no farm is dropped silently.

## Run (macOS)

Needs Docker Desktop and uv (`brew install uv`).

```bash
docker run -d --name farmland-db -e POSTGRES_USER=farmland -e POSTGRES_PASSWORD=farmland \
  -e POSTGRES_DB=farmland_db -p 5434:5432 imresamu/postgis:15-3.4
uv sync
uv run python scripts/ingest.py             # prints "10 farms built, 0 rejected"
uv run uvicorn src.main:app --port 8000
```

Open <http://127.0.0.1:8000/docs> to try the endpoints. To see the farms on a map, paste the reply of `/api/farms` into [geojson.io](https://geojson.io).

## How it works

1. `scripts/ingest.py` reads `data/farmers_data.xls` (10 dummy farms), names the columns and writes the rows to `raw_farms` exactly as typed.
2. In the same transaction it runs `sql/clean_and_build.sql`, so a re-run rebuilds everything or nothing.
3. `clean_corner()` turns each corner string into a point inside India (latitude 6 to 38, longitude 66 to 98), or `NULL` if it cannot be repaired safely.
4. The `farm_candidates` view joins a farm's four points into a convex hull and works out a reject reason, if any. The hull gives the same polygon whatever order the corners were typed in; on this sheet 2 of the 10 farms would otherwise cross themselves.
5. `farms` is a materialized view of the valid farms with polygon, area in m² and GeoJSON; `farm_rejections` lists the rest.
6. The API selects from those two views and does no geometry work per request.

| Typed in the sheet | Result |
| --- | --- |
| `17. 504503, 73.988443` | `17.504503, 73.988443`: the space is removed |
| `185228398, 74.9514` | `18.5228398, 74.9514`: a decimal point goes in after two digits |
| `74.9514, 18.5228` | `18.5228, 74.9514`: latitude and longitude are swapped back |
| `18.52N, 74.95E` | `NULL`: hemisphere letters are not guessed, so the farm is rejected |
| `48.85, 2.35` | `NULL`: outside India |

## API

| Method | Path | What it does |
| --- | --- | --- |
| `GET` | `/health` | Database reachable and the `farms` view built; 200, or 503 |
| `GET` | `/api/farms?limit=&offset=` | All valid farms as a GeoJSON FeatureCollection |
| `GET` | `/api/farms/{farm_id}` | One farm as a GeoJSON Feature, or 404 |
| `GET` | `/api/rejections` | Farms that were left out, with the reason |

The farm id is the sheet's phone column. `DATABASE_URL` defaults to the container above.

## Tests

```bash
uv run pytest -q
```

The corner repair cases and the four endpoints, run against the PostGIS container after `ingest.py`.
