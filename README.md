# Farmland Processing Pipeline 🚜🛰️

## Project Overview

The **Farmland Processing Pipeline** is a production-grade GIS microservice designed to ingest messy, heterogeneous farmland coordinate data and serve perfectly formatted RFC 7946 **GeoJSON (WGS84 - EPSG:4326)**.

Recently refactored for **millions of records**, the system uses a "dumb ingestion" model where raw data is dumped into PostgreSQL, and **PostGIS** handles all the spatial conversions and coordinate math via a highly optimized **Materialized View**. Python is strictly used to serve the pre-calculated geometry, resulting in incredibly fast, scalable read performance.

---

## Key Features

- **🚀 Dumb Ingestion**: Rapidly loads unstructured legacy Excel data into a raw PostgreSQL table using Pandas `to_sql`.
- **🗺️ PostGIS Materialized Views**: Automatically constructs valid polygons from disjointed string columns, formats the data to `EPSG:4326`, and natively repairs spatial anomalies.
- **⚡ Ultra-Fast Serving**: The FastAPI layer simply queries the materialized view and formats the result as a standard `FeatureCollection` with zero coordinate math done in Python.
- **🔄 Concurrent Refreshes**: The PostGIS Materialized view has a unique index, meaning it can be refreshed in the background without blocking reads.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI |
| Database | PostgreSQL + PostGIS |
| DB Driver | SQLAlchemy (Async Core) + Asyncpg |
| Infrastructure | Docker Compose |

*(Note: Previous Python-based GIS dependencies like `Shapely` and `GeoAlchemy2` were removed in favor of native PostGIS processing).*

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
# Dump raw data
python scripts/migrate_to_postgres.py

# Create Materialized View
# Connect to your db and execute scripts/create_materialized_view.sql
# Example: PGPASSWORD=password psql -h localhost -U user -d farmland_db -f scripts/create_materialized_view.sql
```

### 5. Start the Server
> ⚠️ **Always run from the project root directory.**

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

---

*Developed for the Krishi AI Farmland Monitoring Initiative.*
