# Farmland Processing Pipeline 🚜🛰️

## Project Overview

The **Farmland Processing Pipeline** is a robust, enterprise-grade REST API designed to solve the critical challenge of ingesting messy, heterogeneous farmland coordinate data from Krishi Vigyan Kendras (KVKs). 

Built using **FastAPI** and **Shapely**, the system acts as an "aggressive auto-correcting" middleman. It ingests legacy Excel spreadsheets, automatically repairs corrupted GPS data points, and outputs perfectly formatted, machine-learning-ready **GeoJSON (WGS84 - EPSG:4326)**. This clean output is optimized for downstream Sentinel-2 satellite analysis, ensuring that Remote Sensing teams can perform accurate crop monitoring without manual data sanitization.

---

## Key Features (The 'Auto-Fix' Pipeline)

The system is designed to be 100% crash-proof and resilient to common data entry errors:

- **🚀 Dynamic Parsing**: Automatically detects and reads farms with any number of coordinate points, dynamically identifying the starting column (e.g., 'A') and stopping when non-coordinate data is reached.
- **🧹 Data Janitor**: 
    - **Space Eradication**: Automatically strips all accidental whitespace from coordinate strings.
    - **Decimal Auto-Injection**: Detects missing decimal points (e.g., `185228` instead of `18.5228`) and automatically injects them after the second character for consistent float conversion.
- **🛡️ Mathematical Repair (Convex Hull)**: Uses the **Convex Hull** algorithm to automatically resolve self-intersecting "bowtie" polygons caused by out-of-order GPS collection. The system guarantees a mathematically valid, closed-loop Polygon for every success response.
- **📏 High-Precision Normalization**: All coordinates are rounded to 6 decimal places to meet standard remote sensing precision requirements.

---

## Project Structure

```text
farmland-processing-pipeline/
├── src/
│   ├── api/            # Pydantic Schemas and API Routes
│   ├── services/       # Core Business Logic (DB Client & Geometry Processor)
│   ├── data/           # Source Excel Database (farmers_data.xls)
│   ├── static/         # Frontend Dashboard (HTML/CSS/JS)
│   └── main.py         # Application Entry Point
├── venv/               # Virtual Environment
├── requirements.txt    # Python Dependencies
└── README.md           # Documentation
```

---

## Setup & Installation

### 1. Environment Setup
Clone the repository and create a virtual environment:

```bash
# Create virtual environment
python -m venv venv

# Activate on Windows
.\venv\Scripts\activate

# Activate on Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Data Preparation
Place your source spreadsheet strictly at the following location:
`src/data/farmers_data.xls`

*Note: The system supports legacy .xls formats and dynamically searches for the 'Numbers' (Phone) and 'A' (Coordinate) columns.*

---

## Running the Server

Start the production-ready server using Uvicorn:

```bash
uvicorn src.main:app --reload
```

- **Interactive Dashboard**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## API Contract

### Request body
**Endpoint**: `POST /api/process_farm`  
**Primary Key**: `phone_number` (String)

```json
{
  "phone_number": "8805508334"
}
```

### Expected Response (RFC 7946 Compliant)
If the data is messy, the system automatically repairs it and returns a valid `Feature` object:

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
    "crs": {
      "type": "name",
      "properties": { "name": "EPSG:4326" }
    }
  },
  "properties": {
    "status": "success",
    "kvk_number": "8805508334",
    "error_message": null
  }
}
```

---

*Developed for the Krishi AI Farmland Monitoring Initiative.*
