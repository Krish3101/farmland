import httpx
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    FarmFeatureResponse,
    ProcessAndForwardRequest,
    ForwardResponse,
)
from src.services.database import get_db_session
from src.services.db_client import fetch_farm_data
from src.services.farm_processor import process_farm_geometry, GeometryResult

router = APIRouter()


# ── Shared helper ─────────────────────────────────────────────────────────────

async def _get_processed_farm(
    session: AsyncSession, phone_number: str
) -> tuple[FarmFeatureResponse, GeometryResult]:
    """
    Shared internal helper: fetches from PostGIS and applies Silent Healing.
    Raises HTTPException on not-found or processing failure.
    """
    data = await fetch_farm_data(session, phone_number)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"No farmland record found for phone number: {phone_number}",
        )

    result = process_farm_geometry(data["geometry"], data.get("fixes_applied", []))
    if not result.is_valid:
        raise HTTPException(status_code=500, detail=result.error_message)

    feature = FarmFeatureResponse(
        geometry=result.processed_geometry,
        properties={
            "status": result.status,
            "kvk_number": phone_number,
            "fixes_applied": result.fixes_applied,
            "error_message": None,
            "crs": "EPSG:4326",
        },
    )
    return feature, result


# ── GET /api/farm/{phone_number} ──────────────────────────────────────────────

@router.get(
    "/farm/{phone_number}",
    response_model=FarmFeatureResponse,
    summary="Retrieve & auto-clean farmland geometry",
    tags=["Farmland"],
)
async def get_farm(
    phone_number: str,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Retrieves raw coordinate data for the given phone number from PostGIS,
    applies Silent Healing auto-fixes, and returns a strict RFC 7946 GeoJSON Feature.

    **Status values:**
    - `success` — data was clean, no fixes needed.
    - `success_with_fixes` — one or more auto-fixes were applied.

    **Error codes:**
    - `404` — phone number not found in the database.
    - `500` — unexpected internal processing error.
    """
    feature, _ = await _get_processed_farm(session, phone_number)
    return feature


# ── POST /api/process_and_forward ─────────────────────────────────────────────

@router.post(
    "/process_and_forward",
    response_model=ForwardResponse,
    summary="Process farm geometry and forward to a backend module",
    tags=["Integration"],
)
async def process_and_forward(
    request: ProcessAndForwardRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Acts as an intelligent bridge between modules:
    1. Fetches and heals farmland geometry from PostGIS.
    2. Packages it as a strict RFC 7946 GeoJSON Feature.
    3. Asynchronously forwards it via HTTP POST to the specified `target_url`.

    If forwarding fails, returns `partial_success` with the processed payload
    so the caller can retry or inspect the data.
    """
    feature, _ = await _get_processed_farm(session, request.phone_number)

    # Async forward to the target backend module
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                request.target_url,
                json=feature.model_dump(),
                timeout=10.0,
            )
            response.raise_for_status()
    except Exception as e:
        return ForwardResponse(
            status="partial_success",
            message=f"Geometry processed successfully, but forwarding to target failed: {str(e)}",
            target_url=request.target_url,
            forwarded_payload=feature,
        )

    return ForwardResponse(
        status="success",
        message="Farm geometry processed and forwarded to backend module successfully.",
        target_url=request.target_url,
        forwarded_payload=feature,
    )
