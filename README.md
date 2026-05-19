# Farmland Processing Pipeline

## Project Overview

The **Farmland Processing Pipeline** is a comprehensive GIS microservice designed to ingest heterogeneous farmland coordinate data and serve formatted RFC 7946 **GeoJSON (WGS84 - EPSG:4326)**.

Recently refactored for **high volume records**, the system uses a bulk ingestion model where raw data is inserted into PostgreSQL, and **PostGIS** handles all the spatial conversions and coordinate mathematics via an optimized **Materialized View**. Python is strictly used to serve the pre-calculated geometry, resulting in highly performant and scalable read operations.

---

## Key Features

- **Bulk Data Ingestion**: Loads unstructured legacy Excel data into a raw PostgreSQL table using Pandas `to_sql`.
- **PostGIS Materialized Views**: Automatically constructs valid polygons from disjointed string columns, formats the data to `EPSG:4326`, and natively repairs spatial anomalies.
- **Polygon Healing**: Uses `ST_ConvexHull` to eliminate self-intersecting polygons caused by out-of-order coordinate records.
- **High-Performance Serving**: The FastAPI layer queries the materialized view and formats the result as a standard `FeatureCollection` with zero coordinate mathematics done in Python.
- **Concurrent Refreshes**: The PostGIS Materialized view utilizes a unique index, meaning it can be refreshed in the background without blocking read operations.
- **Robust & Scalable**: Includes full `pytest` coverage, PostGIS connection pooling, and paginated GeoJSON endpoints.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI |
| Database | PostgreSQL + PostGIS |
| DB Driver | SQLAlchemy (Async Core) + Asyncpg |
| Infrastructure | Docker Compose |
| Testing | Pytest + httpx |

---

## Project Structure

```text
data-pipeline/
├── src/
│   ├── api/            # API Routes (Serving GeoJSON)
│   ├── services/       # Database Connection Setup
│   ├── data/           # Source Excel file (farmers_data.xls)
│   ├── static/         # Testing Frontend Dashboard (HTML/CSS/JS)
│   └── main.py         # Application Entry Point (FastAPI + lifespan)
├── scripts/
│   ├── migrate_to_postgres.py         # One-time data dump script (Pandas to SQL)
│   └── create_materialized_view.sql   # PostGIS Spatial Conversion logic
├── docker-compose.yml  # PostGIS database 
├── .env.example        # Environment variable template
└── requirements.txt    # Python Dependencies
```

---

## Setup & Installation

### 1. Start the Database
Uses Docker Compose to spin up a PostGIS database:

```bash
docker compose up -d
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env if you use custom DB credentials
```

### 3. Create Virtual Environment & Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

### 4. Run the Data Ingestion & SQL Setup
Loads the raw Excel file into PostGIS and generates the Materialized View:

```bash
# Dump raw data (use --force if tables already exist)
python scripts/migrate_to_postgres.py --force

# Create Materialized View
# Connect to your db and execute scripts/create_materialized_view.sql
# Example: PGPASSWORD=password psql -h localhost -U user -d farmland_db -f scripts/create_materialized_view.sql
```

### 5. Run the Test Suite (Optional)
To verify everything is working, run the integration tests:

```bash
python3 -m pytest tests/ -v
```

### 6. Start the Server
> **Note:** Always run from the project root directory.

```bash
uvicorn src.main:app --reload
```

- **Testing Dashboard**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## API Reference

### GET `/api/farms/geojson`
Retrieve all farmland data formatted as a standard GeoJSON FeatureCollection.

**Example Response (RFC 7946 Compliant):**
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
            [74.951428, 18.522839],
            [74.95174, 18.522633],
            [74.950378, 18.522641],
            [74.950408, 18.522625],
            [74.951428, 18.522839]
          ]
        ]
      },
      "properties": {
        "farm_id": "9272723049"
      }
    }
  ]
}
```
