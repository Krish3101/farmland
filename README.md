# Farmland Processing Pipeline

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL%20%2B%20PostGIS-15-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)

A high-performance GIS microservice built to ingest heterogeneous farmland coordinate data and serve strict RFC 7946 **GeoJSON (WGS84 - EPSG:4326)**. 

Designed for **high volume data**, the architecture uses a two-tier pipeline:
1. **Bulk Ingestion**: Unstructured Excel data is ingested into PostgreSQL.
2. **Spatial Pre-calculation**: PostGIS handles all geometry conversion and coordinate mathematics via an optimized **Materialized View**, bypassing expensive Python spatial math.
3. **Serving**: FastAPI directly queries and serves the pre-computed GeoJSON, maximizing API read throughput.

---

## Quickstart

### 1. Database Setup
Start the local PostGIS container:
```bash
docker compose up -d
```
Copy environment variables and configure them:
```bash
cp .env.example .env
```

### 2. Ingest Data & Setup Views
```bash
# Ingest Excel data to raw tables
uv run python scripts/migrate_to_postgres.py

# Create Materialized Views & Spatial Indexes
PGPASSWORD=password psql -h localhost -p 5434 -U user -d farmland_db -f scripts/create_materialized_view.sql
```

*(To update data later, you can concurrently refresh the view without locking read requests: `REFRESH MATERIALIZED VIEW CONCURRENTLY processed_farm_geojson;`)*

### 3. Run the API
```bash
uv run uvicorn src.main:app --reload --port 8000
```
- **Testing Dashboard**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **API Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Features

- **FastAPI / SQLAlchemy (Async)**: fully asynchronous API design handling concurrent connections efficiently.
- **PostGIS Offloading**: Spatial transformation and validation are shifted entirely to the DB level using Materialized Views.
- **API Key Authentication**: Configurable `X-API-Key` protection on geometry endpoints.
- **Structured Logging**: Emits JSON formatted logs for seamless integration with Datadog, ELK, or CloudWatch.
- **Integration Tests**: 100% automated API endpoint testing using `pytest` and `httpx`.

---

## Project Structure

```text
data-pipeline/
├── src/
│   ├── api/            # Routes & Authentication
│   ├── services/       # Database Connection Pool
│   ├── data/           # Source datasets
│   ├── static/         # Developer testing UI
│   └── main.py         # Entry point & structured logging
├── scripts/
│   ├── migrate_to_postgres.py         # Python ingestion script
│   └── create_materialized_view.sql   # PostGIS conversions
├── docker-compose.yml  # PostGIS service configuration
└── tests/              # Pytest integration suite
```
