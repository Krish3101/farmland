from fastapi import APIRouter, HTTPException
from src.api.schemas import (
    FarmFeatureResponse,
    SentinelSubmitRequest,
    SentinelResponse,
)
from src.services.db_client import fetch_farm_data
from src.services.farm_processor import process_farm_geometry

router = APIRouter()


# ── GET /api/farm/{phone_number} ──────────────────────────────────────────────

@router.get(
    "/farm/{phone_number}",
    response_model=FarmFeatureResponse,
    summary="Retrieve & auto-clean farmland geometry",
    tags=["Farmland"],
)
async def get_farm(phone_number: str):
    """
    Retrieves raw coordinate data for the given phone number, applies Silent
    Healing auto-fixes, processes the geometry with Shapely, and returns a
    strict RFC 7946 GeoJSON Feature.

    All auto-fix actions are recorded in `properties.fixes_applied`.

    **Status values:**
    - `success` — data was clean, no fixes needed.
    - `success_with_fixes` — one or more auto-fixes were applied.

    **Error codes:**
    - `404` — phone number not found in the database.
    - `503` — data source file is missing.
    - `500` — unexpected internal processing error.
    """
    # 1. Fetch + clean data (may raise 503 or 500 HTTPExceptions)
    data = await fetch_farm_data(phone_number)

    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"No farmland record found for phone number: {phone_number}",
        )

    geojson = data["geometry"]
    fixes_applied = data.get("fixes_applied", [])

    # 2. Process geometry — returns a GeometryResult dataclass (M-1 fix)
    result = process_farm_geometry(geojson, fixes_applied)

    if not result.is_valid:
        raise HTTPException(status_code=500, detail=result.error_message)

    # 3. Return strict RFC 7946 GeoJSON Feature (M-3 fix: all custom data in properties)
    return FarmFeatureResponse(
        geometry=result.processed_geometry,
        properties={
            "status": result.status,
            "kvk_number": phone_number,
            "fixes_applied": result.fixes_applied,
            "error_message": None,
            "crs": "EPSG:4326",
        },
    )


# ── POST /api/sentinel/submit ─────────────────────────────────────────────────

@router.post(
    "/sentinel/submit",
    response_model=SentinelResponse,
    summary="Submit GeoJSON payload to Remote Sensing API (simulated)",
    tags=["Sentinel"],
)
async def sentinel_submit(request: SentinelSubmitRequest):
    """
    Accepts a GeoJSON Feature payload and simulates a handoff to the
    Remote Sensing (Sentinel-2) pipeline.

    In production this would forward the payload to an external satellite
    imagery API. Currently returns a mocked success response.
    """
    return SentinelResponse(
        status="success",
        message="Simulated handoff to Remote Sensing API successful.",
    )



