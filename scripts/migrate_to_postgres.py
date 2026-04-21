import asyncio
import json
import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from shapely.geometry import shape, mapping

# Add project root to sys.path to import from src
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.models.base import Base
from src.models.farm import Farm
from src.services.database import DATABASE_URL

# Path to source data
EXCEL_PATH = PROJECT_ROOT / "src" / "data" / "farmers_data.xls"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def migrate():
    # 1. Setup Engine
    engine = create_async_engine(DATABASE_URL)

    # 2. Ingest Excel Data
    if not EXCEL_PATH.exists():
        logger.error("Excel file not found at %s", EXCEL_PATH)
        return

    logger.info("Reading %s ...", EXCEL_PATH)
    try:
        df = pd.read_excel(EXCEL_PATH, engine="xlrd", header=None)
    except Exception as exc:
        logger.error("Failed to read Excel file: %s", exc)
        return

    # Dynamic header discovery (from original script)
    num_col_idx = a_col_idx = None
    header_row_idx = 0

    for r_idx in range(min(15, len(df))):
        row_vals = df.iloc[r_idx].values
        for c_idx, val in enumerate(row_vals):
            s_val = str(val).strip().lower()
            if "numbers" in s_val and num_col_idx is None:
                num_col_idx = c_idx
                header_row_idx = max(header_row_idx, r_idx)
            if s_val == "a" and a_col_idx is None:
                a_col_idx = c_idx
                header_row_idx = max(header_row_idx, r_idx)

    if num_col_idx is None or a_col_idx is None:
        logger.error("Could not locate 'Numbers' or 'A' columns in the Excel file.")
        return

    data_df = df.iloc[header_row_idx + 1 :].copy()

    # 3. Handle Database Schema
    async with engine.begin() as conn:
        # Enable PostGIS extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        # Drop and Recreate tables (standard for this one-time migration)
        # Note: metadata.drop_all/create_all are sync, so we use run_sync
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("PostGIS extension enabled and tables created.")

    # 4. Processing & Insertion Loop
    inserted = skipped = 0
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        for _, row in data_df.iterrows():
            phone_val = row[num_col_idx]
            if pd.isna(phone_val):
                continue

            phone_number = str(phone_val).strip()
            if phone_number.endswith(".0"):
                phone_number = phone_number[:-2]

            fixes_set = set()
            polygon_array = []
            row_data = row.values

            # Silent Healing Loop (same as original)
            for c_idx in range(a_col_idx, len(row_data)):
                val = row_data[c_idx]
                if pd.isna(val) or str(val).strip() == "":
                    break

                raw_str = str(val)
                if " " in raw_str:
                    fixes_set.add("Removed accidental spaces from coordinates.")
                s_val = raw_str.replace(" ", "")

                if "," not in s_val:
                    break

                try:
                    lat_str, lon_str = s_val.split(",", 1)
                    if "." not in lat_str and len(lat_str) > 2:
                        lat_str = lat_str[:2] + "." + lat_str[2:]
                        fixes_set.add("Injected missing decimal point.")
                    if "." not in lon_str and len(lon_str) > 2:
                        lon_str = lon_str[:2] + "." + lon_str[2:]
                        fixes_set.add("Injected missing decimal point.")

                    polygon_array.append(
                        [round(float(lon_str), 6), round(float(lat_str), 6)]
                    )
                except (ValueError, IndexError):
                    break

            if len(polygon_array) < 3:
                skipped += 1
                continue

            # Close loop
            polygon_array.append(polygon_array[0].copy())

            raw_geometry = {"type": "Polygon", "coordinates": [polygon_array]}
            
            try:
                geom = shape(raw_geometry)
                if not geom.is_valid:
                    geom = geom.convex_hull
                    fixes_set.add("Aggressive Fix: Repaired self-intersecting geometry via Convex Hull.")
                
                # Convert Shapely object to WKT for PostGIS insertion
                # GeoAlchemy2 prefers WKT or WKB
                wkt_geom = geom.wkt
                
                farm = Farm(
                    phone_number=phone_number,
                    geom=f"SRID=4326;{wkt_geom}",
                    fixes_applied=list(sorted(fixes_set))
                )
                session.add(farm)
                inserted += 1

            except Exception as exc:
                logger.warning("Could not repair geometry for %s: %s", phone_number, exc)
                skipped += 1
                continue

        await session.commit()

    logger.info("Migration complete. %d records inserted, %d skipped.", inserted, skipped)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
