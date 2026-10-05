# Farmland

Hand-typed GPS corner strings are cleaned in SQL into validated farm polygons; farms that can't be repaired are listed with a reason.

All rows in `data/farmers_data.xls` are dummy data.

**Stack:** PostgreSQL with PostGIS, FastAPI, async SQLAlchemy with asyncpg, pandas for loading the spreadsheet, Docker Compose for the database.

## How the cleaning works

Each farm in the spreadsheet has four GPS corners typed by hand, so the values are messy: stray spaces, missing decimal points, latitude and longitude swapped, degree signs. All of the cleaning happens in the database.

    data/farmers_data.xls
      -> scripts/ingest.py           loads the sheet as-is into raw_farmers_data (one transaction)
      -> sql/clean_and_build.sql     runs in one transaction (psql -1, ON_ERROR_STOP)
           clean_coordinate()        repair one corner, or return NULL
           farm_candidates           four corners per farm, convex hull, reject_reason
           ST_ForcePolygonCCW        exterior ring counter-clockwise (RFC 7946)
           ST_Area(geography)        area_m2
           ST_AsGeoJSON              serialised once, stored as JSON
      -> processed_farm_geojson      materialized view of valid farms, unique index on farm_id
      -> farm_rejections             view of every farm left out, with the reason
      -> src/api.py                  plain indexed lookup, no geometry math per request

The cleaning and geometry run in PostGIS rather than Python. The work is done once when the view is refreshed instead of on every request, so a read is just an indexed lookup against JSON that is already serialised. The unique index on `farm_id` is what allows `REFRESH MATERIALIZED VIEW CONCURRENTLY`, so the data can be rebuilt without blocking reads. The cost is that reads are eventually consistent: after re-ingesting the spreadsheet you have to refresh the view or the API keeps serving the old geometry. `scripts/ingest.py` does that refresh itself when the view already exists.

**Repairing a corner.** `clean_coordinate()` takes one `"lat,lon"` string and:

1. strips whitespace and degree signs (`17. 504503, 73.988443` becomes `17.504503,73.988443`);
2. inserts a missing decimal point after two digits (`185228398` becomes `18.5228398`);
3. swaps latitude and longitude if they were typed the wrong way round;
4. checks the point lies inside India (latitude 6 to 38, longitude 66 to 98).

Anything else returns `NULL`: hemisphere letters, signs, decimal commas, `NaN`, out-of-range values. `tests/test_cleaning.py` covers 25 of these inputs.

**Why a convex hull.** The four corners are joined with `ST_ConvexHull`, so the polygon doesn't depend on the order they were typed in. On this sheet, 8 of the 10 rings in typed order are valid and have exactly the hull's area; the other 2 cross themselves (a bow-tie). One farm has two identical corners, so its hull is a triangle, which is still a valid polygon.

Every polygon is valid and counter-clockwise, and `area_m2` is its area in square metres on the WGS84 spheroid.

## Rejections

A farm is never dropped silently. `farm_candidates` gives each farm a `reject_reason`, and the `farm_rejections` view lists every farm with one:

| Reason | When |
|---|---|
| `duplicate farm_id` | the same id appears more than once (all copies are rejected, none is picked) |
| `corner A unparseable` (B, C, D) | `clean_coordinate()` returned `NULL` for that corner |
| `corners collinear or identical` | the hull is a line or a point, not a polygon |

`./scripts/start.sh` prints the count after the first build, and `scripts/ingest.py` prints it after each refresh. The shipped sheet has 0 rejections. To see them:

```bash
docker compose exec db psql -U farmland -d farmland_db -c "SELECT * FROM farm_rejections"
```

## Run

Requires Docker, [uv](https://docs.astral.sh/uv/) and `openssl`.

```bash
./scripts/start.sh
```

On the first run it copies `.env.example` to `.env` and fills the empty `POSTGRES_PASSWORD`, `DATABASE_URL` and `API_KEY` with random values. It then starts PostGIS, loads the spreadsheet, builds the cleaning function and views, prints the rejection count, and runs the API on <http://127.0.0.1:8000>. On later runs it just starts the API.

To start from scratch, run `docker compose down -v` and delete `.env` together; a new `.env` has a new password that the old database volume would refuse.

## API

| Endpoint | Auth | Description |
|---|---|---|
| `GET /health` | none | Database reachable and the view built |
| `GET /api/farms/geojson` | `X-API-Key` | GeoJSON FeatureCollection; query params `farm_id`, `limit` (1 to 1000, default 100), `offset` |

`farm_id` filters to one farm and still respects `limit` and `offset`; an empty `farm_id` means no filter. OpenAPI docs are at `/docs`.

```bash
API_KEY=$(grep '^API_KEY=' .env | cut -d= -f2)
curl -H "X-API-Key: $API_KEY" "http://127.0.0.1:8000/api/farms/geojson?limit=1"
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
            [75.237454, 17.943258],
            [75.237671, 17.944271],
            [75.237287, 17.944327],
            [75.237089, 17.943318],
            [75.237454, 17.943258]
          ]
        ]
      },
      "properties": { "farm_id": "8805508334", "area_m2": 4580.5 }
    }
  ]
}
```

## Configuration

All values live in `.env` (see `.env.example`). `start.sh` fills the empty secrets.

| Variable | Used by | Notes |
|---|---|---|
| `API_KEY` | API | Required; the API refuses to start without it. Clients send it as `X-API-Key`. |
| `DATABASE_URL` | API, ingest, tests | `postgresql+asyncpg://user:password@localhost:5434/farmland_db`. No default. |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Compose | The password is required; Compose won't start without it. |
| `DB_PORT` | Compose | Port on 127.0.0.1 for PostGIS, default 5434 so it doesn't clash with a local Postgres. |

## Tests

```bash
uv run pytest -v -rs
uv run ruff check . && uv run ruff format --check .
```

Most tests need the PostGIS database with the sheet loaded and the SQL built (`./scripts/start.sh` does this); they find it through `DATABASE_URL` in `.env`. Without it they are skipped, and `-rs` shows why. Setting `REQUIRE_DB=1` turns an unreachable database into an error instead of skips.

## Layout

```text
sql/clean_and_build.sql   cleaning function, candidate and rejection views, materialized view
scripts/ingest.py         loads the spreadsheet into raw_farmers_data
scripts/start.sh          secrets, database, ingest, SQL build, API
src/main.py               app, startup check for API_KEY, /health
src/db.py                 async engine and session
src/api.py                API key check and the GeoJSON endpoint
tests/test_cleaning.py    clean_coordinate() cases and view invariants (DB tests)
tests/test_api.py         endpoint, auth and pagination tests
```

## Limitations

- **India only:** corners outside latitude 6 to 38 and longitude 66 to 98 are rejected.
- **No guessing:** 1-digit latitudes without a decimal point and hemisphere letters (`N`, `E`) are rejected, not guessed.
- **Phone number as id:** `farm_id` is the spreadsheet's phone column, which is fine for dummy data but not for real farms.
- **Fixed columns:** the SQL reads the spreadsheet's columns by position (`Unnamed: 3`, `Unnamed: 7` to `Unnamed: 10`); a different layout needs the view updated.

## License

[MIT](LICENSE)
