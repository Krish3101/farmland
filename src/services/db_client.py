"""
src/services/db_client.py
--------------------------
Async database client for the Farmland Processing Pipeline.

Reads pre-cleaned farm geometry from src/data/farmland.db via aiosqlite.
The .db file is populated once by scripts/migrate_to_sqlite.py.

Raises:
    HTTPException(503): farmland.db file is missing.
    HTTPException(500): unexpected error during query.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import aiosqlite
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Absolute path — works no matter what CWD the server is launched from
_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "farmland.db"


async def fetch_farm_data(phone_number: str) -> Optional[Dict[str, Any]]:
    """
    Look up a farmer by phone number and return pre-cleaned geometry.

    Returns:
        dict with keys: kvk_number, geometry (GeoJSON dict), fixes_applied (list[str])
        None if no record found for the given phone number.

    Raises:
        HTTPException(503): farmland.db is missing — run the migration script.
        HTTPException(500): unexpected internal error.
    """
    if not _DB_PATH.exists():
        logger.error("Database not found: %s", _DB_PATH)
        raise HTTPException(
            status_code=503,
            detail=(
                "Data source unavailable. farmland.db is missing — "
                "run scripts/migrate_to_sqlite.py to generate it."
            ),
        )

    try:
        async with aiosqlite.connect(_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT geometry, fixes_applied FROM farms WHERE phone_number = ?",
                (str(phone_number).strip(),),
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        geometry_json, fixes_json = row
        return {
            "kvk_number": phone_number,
            "geometry": json.loads(geometry_json),
            "fixes_applied": json.loads(fixes_json),
        }

    except HTTPException:
        raise  # re-raise 503 without wrapping
    except Exception as exc:
        logger.error(
            "Unexpected error fetching farm data for %s: %s",
            phone_number,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal error while fetching farm data: {exc}",
        )
