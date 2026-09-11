import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import verify_api_key
from src.services.database import get_db_session

logger = logging.getLogger(__name__)

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
        examples=["9000000001"],
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
    as a standard GeoJSON FeatureCollection. All spatial processing is
    handled entirely within PostGIS.

    - **farm_id**: Filter by a specific farm ID (phone number).
    - **limit**: Max features per page (default 100, max 1000).
    - **offset**: Skip N features for pagination.
    """
    try:
        if farm_id:
            query = text(
                "SELECT farm_id, geojson FROM processed_farm_geojson WHERE farm_id = :farm_id"
            )
            result = await session.execute(query, {"farm_id": farm_id})
        else:
            query = text(
                "SELECT farm_id, geojson FROM processed_farm_geojson "
                "ORDER BY farm_id LIMIT :limit OFFSET :offset"
            )
            result = await session.execute(query, {"limit": limit, "offset": offset})

        features = []
        for row in result.all():
            farm_id_val, geojson_data = row

            # The geojson column could be returned as a dict or string depending on the driver
            geometry = geojson_data if isinstance(geojson_data, dict) else json.loads(geojson_data)

            feature = {
                "type": "Feature",
                "geometry": geometry,
                "properties": {"farm_id": farm_id_val},
            }
            features.append(feature)

        feature_collection = {"type": "FeatureCollection", "features": features}

        return feature_collection

    except Exception as exc:
        logger.error("Error fetching geojson data: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve processed farm GeoJSON.",
        ) from exc
