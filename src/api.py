import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db_session

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(request: Request, api_key: str = Security(api_key_header)):
    """Compare the X-API-Key header with the key read at startup."""
    expected = request.app.state.api_key
    if not api_key or not secrets.compare_digest(api_key.encode(), expected.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API Key."
        )
    return api_key


router = APIRouter()


@router.get(
    "/farms/geojson",
    summary="Get processed farms as a standard GeoJSON FeatureCollection",
    tags=["Farmland"],
    dependencies=[Depends(verify_api_key)],
)
async def get_farms_geojson(
    farm_id: str | None = Query(
        None,
        description="Optional farm ID (phone number) to filter a specific farm.",
        examples=["8805508334"],
        max_length=64,
        # Postgres text can't hold a NUL byte; reject it here instead of failing the query.
        pattern=r"^[^\x00]*$",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of features to return.",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of features to skip (for pagination).",
    ),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Returns farms from the `processed_farm_geojson` materialized view
    as a GeoJSON FeatureCollection, with each farm's area in square metres.
    """
    # An empty farm_id means no filter; limit/offset apply either way.
    query = text(
        "SELECT farm_id, area_m2, geojson FROM processed_farm_geojson "
        "WHERE (CAST(:farm_id AS text) IS NULL OR farm_id = :farm_id) "
        "ORDER BY farm_id LIMIT :limit OFFSET :offset"
    )
    params = {"farm_id": (farm_id or "").strip() or None, "limit": limit, "offset": offset}
    try:
        result = await session.execute(query, params)
    except Exception as exc:
        logger.error("Error fetching geojson data: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve processed farm GeoJSON.",
        ) from exc

    features = [
        {
            "type": "Feature",
            "geometry": geojson,
            "properties": {"farm_id": row_farm_id, "area_m2": float(area_m2)},
        }
        for row_farm_id, area_m2, geojson in result.all()
    ]
    return {"type": "FeatureCollection", "features": features}
