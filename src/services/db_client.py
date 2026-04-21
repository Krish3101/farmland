"""
src/services/db_client.py
--------------------------
Database client for the Farmland Processing Pipeline.
Uses SQLAlchemy to interface with PostGIS.
"""
import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.farm import Farm

logger = logging.getLogger(__name__)


async def fetch_farm_data(session: AsyncSession, phone_number: str) -> Optional[Dict[str, Any]]:
    """
    Look up a farmer by phone number and return cleaned geometry.

    Args:
        session: Async SQLAlchemy session.
        phone_number: Farmer's phone number.

    Returns:
        dict with keys: kvk_number, geometry (GeoJSON dict), fixes_applied (list[str])
        None if no record found.
    """
    try:
        # Use ST_AsGeoJSON to get the geometry as a GeoJSON string directly from PostGIS
        stmt = select(
            Farm.phone_number,
            func.ST_AsGeoJSON(Farm.geom).label("geometry_json"),
            Farm.fixes_applied
        ).where(Farm.phone_number == str(phone_number).strip())
        
        result = await session.execute(stmt)
        row = result.fetchone()

        if row is None:
            return None

        return {
            "kvk_number": row.phone_number,
            "geometry": json.loads(row.geometry_json),
            "fixes_applied": row.fixes_applied,
        }

    except Exception as exc:
        logger.error(
            "Unexpected error fetching farm data for %s: %s",
            phone_number,
            exc,
            exc_info=True,
        )
        return None
