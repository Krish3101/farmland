# Farmland Processing Pipeline 🚜🛰️

## Project Overview

The **Farmland Processing Pipeline** is a production-grade GIS microservice designed to solve the critical challenge of ingesting messy, heterogeneous farmland coordinate data from Krishi Vigyan Kendras (KVKs).

Built using **FastAPI**, **PostgreSQL/PostGIS**, and **Shapely**, the system acts as an intelligent "Silent Healing" bridge. It reads farm records from a PostGIS database, automatically repairs corrupted GPS data, and outputs perfectly formatted RFC 7946 **GeoJSON (WGS84 - EPSG:4326)**.

This clean output can be consumed directly by the testing dashboard or forwarded programmatically to any downstream backend module (e.g., a Remote Sensing or ML pipeline).

---

## Key Features (The 'Silent Healing' Pipeline)

The system is designed to be 100% crash-proof and resilient to real-world field data errors:

- **🚀 Dynamic Parsing**: Automatically detects and reads farms with any number of coordinate points from legacy Excel spreadsheets.
- **🧹 Data Janitor**:
    - **Space Eradication**: Automatically strips all accidental whitespace from coordinate strings.
    - **Decimal Auto-Injection**: Detects and fixes numbers like `185228` → `18.5228`.
- **🔄 India Bounds Lat/Lon Swap**: If GPS coordinates appear to be outside India's geographic bounds (`6°N–38°N`, `66°E–98°E`), the system automatically detects and corrects swapped Latitude/Longitude values — a common field data entry error.
- **🛡️ Topology Repair**: Uses `buffer(0)` to untangle self-intersecting "bowtie" polygons while **preserving the original farm shape**. Falls back to Convex Hull only as a last resort.
- **📏 High-Precision Normalization**: All coordinates are rounded to 6 decimal places.
- **🔗 Module Forwarding**: A dedicated endpoint accepts a `phone_number` and `target_url`, heals the data, and automatically POSTs the GeoJSON to a downstream backend module.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI |
| Database | PostgreSQL + PostGIS |
| ORM | SQLAlchemy (Async) + GeoAlchemy2 |
| Geometry Engine | Shapely |
| HTTP Client | HTTPX (async forwarding) |
| Infrastructure | Docker Compose (OrbStack) |

---

## Project Structure

```text
data-pipeline/
├── src/
│   ├── api/            # Pydantic Schemas and API Routes
│   ├── models/         # SQLAlchemy ORM Models (Farm + Base)
│   ├── services/       # Core Business Logic (DB Client, Geometry Processor)
│   ├── data/           # Source Excel file (farmers_data.xls)
│   ├── static/         # Testing Frontend Dashboard (HTML/CSS/JS)
│   └── main.py         # Application Entry Point (FastAPI + lifespan)
├── scripts/
│   └── migrate_to_postgres.py  # One-time data migration script
├── docker-compose.yml  # PostGIS database (OrbStack compatible)
├── .env.example        # Environment variable template
└── requirements.txt    # Python Dependencies
```

---

## Setup & Installation

### 1. Start the Database
Uses Docker Compose (works out of the box with OrbStack):

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

### 4. Run the Data Migration
Loads the source Excel file into PostGIS:

```bash
python scripts/migrate_to_postgres.py
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

### GET `/api/farm/{phone_number}`
Retrieve and auto-heal geometry for a specific farmer.

**Example Response (RFC 7946 Compliant):**
```json
{
  "type": "Feature",
  "geometry": {
    "type": "Polygon",
    "coordinates": [
      [
        [75.220225, 17.937005],
        [75.22145, 17.937174],
        [75.221415, 17.937551],
        [75.220145, 17.93736],
        [75.220225, 17.937005]
      ]
    ],
    "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
  },
  "properties": {
    "status": "success_with_fixes",
    "kvk_number": "8805508334",
    "fixes_applied": ["Repaired self-intersecting polygon using topology fix (buffer(0))."],
    "error_message": null,
    "crs": "EPSG:4326"
  }
}
```

### POST `/api/process_and_forward`
Heal geometry and forward the result to a downstream backend module.

**Request Body:**
```json
{
  "phone_number": "8805508334",
  "target_url": "http://your-backend-module/api/receive"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Farm geometry processed and forwarded to backend module successfully.",
  "target_url": "http://your-backend-module/api/receive",
  "forwarded_payload": { ... }
}
```

---

*Developed for the Krishi AI Farmland Monitoring Initiative.*
