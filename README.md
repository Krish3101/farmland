# Farmland

A REST API that turns a hand-typed farmland spreadsheet into validated field
boundaries and serves them as GeoJSON (RFC 7946, EPSG:4326).

## What it does

Each farm in the source spreadsheet has four GPS corners, typed by hand, so the
values are inconsistent. The cleaning step handles:

- extra whitespace inside the coordinate string
- a missing decimal point (`185228398` becomes `18.5228398`)
- latitude and longitude entered the wrong way round
- values that are not numeric at all, which are rejected

A farm is only included if all four of its corners clean successfully. The four
points are then turned into a polygon with `ST_ConvexHull`, which avoids having
to guess the order the corners were entered in.

## How it works

    farmers_data.xls
      -> migrate_to_postgres.py    loads the sheet verbatim into raw_farmers_data
      -> create_materialized_view.sql
           clean_coordinate()      whitespace, decimals, lat/lon swap, type check
           ST_ConvexHull           four corners into a polygon
           ST_MakeValid            fix self-intersections
           ST_SetSRID(4326)        tag as WGS84
           ST_AsGeoJSON            serialise once, store as JSON
      -> processed_farm_geojson    materialized view, unique index on farm_id
      -> FastAPI                   plain indexed lookup, no geometry math per request

The cleaning and geometry run in PostGIS rather than Python. The work is done
once when the view is refreshed instead of on every request, so a read is just
an indexed lookup against JSON that is already serialised. The unique index on
`farm_id` is what allows `REFRESH MATERIALIZED VIEW CONCURRENTLY`, so the data
can be rebuilt without blocking reads. The cost is that reads are eventually
consistent: after re-ingesting the spreadsheet you have to refresh the view or
the API keeps serving the old geometry.

## Setup

Needs Python 3.10+, Docker, and [uv](https://docs.astral.sh/uv/).

```bash
./scripts/start.sh
```

That does everything below in order: creates `.env`, starts PostGIS, waits for it, loads
the spreadsheet, builds the view, and runs the API on <http://127.0.0.1:8000>. It only
ingests when `raw_farmers_data` doesn't exist yet, so running it again just starts the API.
`./scripts/reset.sh` drops the database volume and the local virtualenv, after asking first.

The rest of this section is what the script does, step by step, if you would rather run it
yourself or need to change part of it.

Create your env file first, since compose reads it:

```bash
cp .env.example .env
```

Set `API_KEY` in `.env` to any value. The geometry endpoint checks against it.

Start the database:

```bash
docker compose up -d db
```

Load the spreadsheet and build the view:

```bash
uv run --group scripts python scripts/migrate_to_postgres.py
```

The ingestion script needs pandas, xlrd and psycopg2, which are in the optional
`scripts` dependency group. The API itself does not depend on them.

```bash
docker compose exec -T db psql -U user -d farmland_db \
  < scripts/create_materialized_view.sql
```

This runs psql inside the database container, so you do not need the Postgres
client tools installed locally. If you do have them, the equivalent is
`PGPASSWORD=password psql -h localhost -p 5434 -U user -d farmland_db -f scripts/create_materialized_view.sql`.

Run the API:

```bash
uv run uvicorn src.main:app --reload --port 8000
```

Dashboard at <http://127.0.0.1:8000>, Swagger UI at `/docs`, health check at
`/health`.

To run the API in a container instead of locally, `docker compose up -d` starts
both services and puts the API on port 8005.

After re-ingesting the spreadsheet, refresh the view:

```bash
docker compose exec -T db psql -U user -d farmland_db \
  -c 'REFRESH MATERIALIZED VIEW CONCURRENTLY processed_farm_geojson;'
```

## API

See [docs/API_REFERENCE.md](docs/API_REFERENCE.md) for the full reference.

| Endpoint | Auth | Description |
|---|---|---|
| `GET /` | none | Leaflet dashboard, looks up a farm by ID |
| `GET /health` | none | Runs `SELECT 1` against the database |
| `GET /docs` | none | Swagger UI |
| `GET /api/farms/geojson` | `X-API-Key` | FeatureCollection; takes `farm_id`, `limit` (1-1000), `offset` |

```bash
curl -H "X-API-Key: $API_KEY" \
  "http://127.0.0.1:8000/api/farms/geojson?limit=10&offset=0"
```

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[74.9503787, 18.5226414], [74.950408, 18.5226259]]]
      },
      "properties": { "farm_id": "9000000001" }
    }
  ]
}
```

## Tests

```bash
uv run pytest
```

Tests run against the real ASGI app through httpx. The ones needing live data are
marked `@requires_db` and skip when PostGIS is not reachable, so a fresh checkout
still runs clean — about half the suite skips without Docker and all of it runs with it.

They cover auth (missing key, wrong key, unconfigured server), pagination
validation, GeoJSON structure and geometry types, and the 503 path when the
database is down.

Linting and formatting use [ruff](https://docs.astral.sh/ruff/):

```bash
uv run ruff check .
uv run ruff format .
```

## Layout

```text
src/
  main.py              app setup, CORS, JSON logging, /health
  api/routes.py        GeoJSON endpoint
  api/auth.py          X-API-Key dependency
  services/database.py async engine and session dependency
  static/              Leaflet dashboard
  data/                source spreadsheet
scripts/
  start.sh                      database, ingest, view, API
  reset.sh                      drop the volume and start over
  migrate_to_postgres.py        spreadsheet into raw_farmers_data
  create_materialized_view.sql  cleaning, geometry, index
tests/                 pytest suite
docs/API_REFERENCE.md  endpoint reference
```

## Known limitations

`farm_id` is the farmer's phone number. It came from the source data and works as
a natural key, but it is personal data and it can change hands, so a surrogate ID
would be better.

The view reads columns named `"Unnamed: 3"` and similar. The spreadsheet has a
two-row header, so pandas auto-names every column and the SQL ends up coupled to
that. Renaming the columns during ingestion would fix it.

The sample dataset is small. The design is meant to scale, since geometry cost is
paid at refresh time rather than per request, but that is an argument rather than
a benchmark.

## License

[MIT](LICENSE)
