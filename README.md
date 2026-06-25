# Farmland Processing Pipeline

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL%20%2B%20PostGIS-15-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

## Project Overview

The **Farmland Processing Pipeline** is a comprehensive GIS microservice designed to ingest heterogeneous farmland coordinate data and serve formatted RFC 7946 **GeoJSON (WGS84 - EPSG:4326)**.

Recently refactored for **high volume records**, the system uses a bulk ingestion model where raw data is inserted into PostgreSQL, and **PostGIS** handles all the spatial conversions and coordinate mathematics via an optimized **Materialized View**. Python is strictly used to serve the pre-calculated geometry, resulting in highly performant and scalable read operations.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI |
| Database | PostgreSQL + PostGIS |
| DB Driver | SQLAlchemy (Async Core) + Asyncpg |
| Infrastructure | Docker Compose / Standalone PostGIS |
| Package Manager | `uv` / pip |
| Testing | Pytest + httpx |

---

## Setup & Running PostGIS Pipeline Independently

This pipeline is 100% self-contained and can be run independently of other microservices. You only need a PostGIS-enabled database and Python.

### 1. Configure the Database
You can spin up a dedicated PostGIS database locally using the provided Docker Compose configuration, or connect to a remote instance.

To run via Docker:
```bash
docker compose up -d
```
*(This starts a PostGIS 15 container bound to port `5432` with username `user`, password `password`, and database `farmland_db`).*

### 2. Configure Environment Variables
Copy the environment template:
```bash
cp .env.example .env
```
Fill in the credentials matching your database and API security choices (see [API Endpoint Security & Authentication](#api-endpoint-security--authentication) below).

### 3. Setup Virtual Environment & Install Dependencies
Activate your virtual environment and install dependencies using `uv` (recommended) or pip.

**On macOS/Linux:**
```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

**On Windows (PowerShell):**
```powershell
uv venv
.venv\Scripts\activate
uv pip install -r requirements.txt
```

---

## Database Migrations

The database migration and setup process consists of two stages: loading raw source data and constructing the spatial materialized views.

### Step 1: Ingest Excel Data to PostgreSQL Table
Run the migration script to parse the Excel file (`src/data/farmers_data.xls`) and load the raw unstructured data into the `raw_farmers_data` table.

```bash
# Truncates and populates the raw data table
uv run python scripts/migrate_to_postgres.py --force
```

### Step 2: Set Up Spatial PostGIS Geometry & Materialized View
Run the SQL script to create geometry conversion functions, set up the materialized view, and define unique indexing. This is done by connecting to the PostgreSQL container and piping the SQL file.

**Using `psql` (Recommended):**
```bash
PGPASSWORD=password psql -h localhost -p 5432 -U user -d farmland_db -f scripts/create_materialized_view.sql
```
*Note: Replace credentials if using custom ones in `.env`.*

#### Materialized View Refresh
Whenever raw data changes, you can perform a fast, concurrent refresh of the materialized view without locking read requests:
```bash
PGPASSWORD=password psql -h localhost -p 5432 -U user -d farmland_db -c "REFRESH MATERIALIZED VIEW CONCURRENTLY processed_farm_geojson;"
```

---

## Running the Application

### Start the FastAPI Server
Run the FastAPI development server from the project root:
```bash
uv run uvicorn src.main:app --reload --port 8000
```
- **Testing Dashboard**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Run Tests
To verify the application integration and correctness, run the test suite:
```bash
uv run pytest tests/ -v
```
*(Tests require a running database and the materialized view setup. The test client automatically overrides the database connection to use test-specific configurations).*

---

## API Endpoint Security & Authentication

Endpoints serving sensitive geometry (e.g., `GET /api/farms/geojson`) are protected by API Key Header authentication.

1. **Configuration**: Define the key on the server in the `.env` file:
   ```env
   API_KEY=your_secure_api_key_here
   ```
2. **Accessing protected endpoints**: Pass the key in the request using the `X-API-Key` HTTP Header.
   
   **Example Request via curl:**
   ```bash
   curl -H "X-API-Key: your_secure_api_key_here" http://127.0.0.1:8000/api/farms/geojson
   ```
3. **Response Status Codes**:
   - **200 OK**: Request is authenticated and processed successfully.
   - **401 Unauthorized**: Key is missing or invalid.
   - **500 Internal Server Error**: Key is not configured on the server.

---

## Logging Configuration (Structured JSON Logs)

The Farmland Processing Pipeline uses a custom `JSONFormatter` in `src/main.py` for all logs. This formats standard Python logs into structured JSON strings suitable for centralized logging systems (e.g., Datadog, ELK stack, AWS CloudWatch).

### JSON Log Output Structure
Each log entry is printed to stdout in the following format:
```json
{
  "timestamp": "2026-06-01 22:15:30",
  "level": "INFO",
  "logger": "src.main",
  "message": "Farmland Processing Pipeline starting up...",
  "exception": "Traceback if error occurred..."
}
```

### Log Customization
- **Output Destination**: Logs are written directly to stdout so container platforms (e.g., Docker, Kubernetes) can ingest them natively.
- **Log Level**: The log level can be set to `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` via the `.env` file:
  ```env
  LOG_LEVEL=INFO
  ```

---

## Project Structure

```text
data-pipeline/
├── src/
│   ├── api/            # API endpoints & Authentication dependencies
│   ├── services/       # Database Connection Pool (SQLAlchemy)
│   ├── data/           # Source Excel file (farmers_data.xls)
│   ├── static/         # Frontend dashboard (HTML/CSS/JS)
│   └── main.py         # FastAPI App Entry point & JSON Logging setup
├── scripts/
│   ├── migrate_to_postgres.py         # Python Pandas data loader
│   └── create_materialized_view.sql   # PostGIS Spatial Conversion SQL
├── docker-compose.yml  # PostGIS service
├── .env.example        # Env templates
├── requirements.txt    # Python Dependencies
├── pyproject.toml      # Dependency & Package configurations
└── pytest.ini          # Pytest configurations
```
