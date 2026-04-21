"""
scripts/migrate_to_sqlite.py
----------------------------
One-time migration script: reads src/data/farmers_data.xls, applies the
exact "Silent Healing" logic used by the original db_client.py, and
populates src/data/farmland.db with pre-cleaned JSON for instant API reads.

Run from the project root:
    python scripts/migrate_to_sqlite.py
"""
import json
import logging
import sqlite3
import sys
from pathlib import Path

import pandas as pd
from shapely.geometry import shape, mapping

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXCEL_PATH   = PROJECT_ROOT / "src" / "data" / "farmers_data.xls"
DB_PATH      = PROJECT_ROOT / "src" / "data" / "farmland.db"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def migrate() -> None:
    if not EXCEL_PATH.exists():
        logger.error("Excel file not found at %s", EXCEL_PATH)
        sys.exit(1)

    logger.info("Reading %s …", EXCEL_PATH)
    try:
        df = pd.read_excel(EXCEL_PATH, engine="xlrd", header=None)
    except Exception as exc:
        logger.error("Failed to read Excel file: %s", exc)
        sys.exit(1)

    # ── Dynamic header discovery ───────────────────────────────────────────────
    num_col_idx: int | None = None
    a_col_idx:   int | None = None
    header_row_idx: int = 0

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
        sys.exit(1)

    data_df = df.iloc[header_row_idx + 1 :].copy()

    # ── SQLite setup ───────────────────────────────────────────────────────────
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS farms")
    cursor.execute(
        """
        CREATE TABLE farms (
            phone_number  TEXT PRIMARY KEY,
            geometry      JSON NOT NULL,
            fixes_applied JSON NOT NULL
        )
        """
    )

    logger.info("Applying Silent Healing and inserting rows …")
    inserted = skipped = 0

    for _, row in data_df.iterrows():
        phone_val = row[num_col_idx]
        if pd.isna(phone_val):
            continue

        phone_number: str = str(phone_val).strip()
        if phone_number.endswith(".0"):
            phone_number = phone_number[:-2]

        fixes_set: set[str] = set()
        polygon_array: list[list[float]] = []
        row_data = row.values

        # ── Silent Healing loop ────────────────────────────────────────────────
        for c_idx in range(a_col_idx, len(row_data)):
            val = row_data[c_idx]
            if pd.isna(val) or str(val).strip() == "":
                break

            raw_str = str(val)

            # Auto-Fix 1: remove accidental spaces
            if " " in raw_str:
                fixes_set.add("Removed accidental spaces from coordinates.")
            s_val = raw_str.replace(" ", "")

            if "," not in s_val:
                break

            try:
                # W-6 fix: maxsplit=1 prevents crash on multi-comma cells
                lat_str, lon_str = s_val.split(",", 1)

                # Auto-Fix 2: inject missing decimal after 2nd character
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

        # Close the loop
        polygon_array.append(polygon_array[0].copy())

        raw_geometry = {"type": "Polygon", "coordinates": [polygon_array]}
        
        # ── Aggressive Auto-Fixer: Geometry Repair ──
        try:
            geom = shape(raw_geometry)
            if not geom.is_valid:
                geom = geom.convex_hull
                fixes_set.add("Aggressive Fix: Repaired self-intersecting geometry via Convex Hull.")
            
            # Rebuild GeoJSON structure from corrected Shapely object
            geometry = mapping(geom)
            
            # Append official CRS info
            geometry["crs"] = {
                "type": "name",
                "properties": {"name": "EPSG:4326"}
            }
        except Exception as exc:
            logger.warning("Could not repair geometry for %s: %s", phone_number, exc)
            skipped += 1
            continue

        fixes_applied: list[str] = sorted(fixes_set)

        cursor.execute(
            "INSERT OR REPLACE INTO farms (phone_number, geometry, fixes_applied) "
            "VALUES (?, ?, ?)",
            (phone_number, json.dumps(geometry), json.dumps(fixes_applied)),
        )
        inserted += 1

    conn.commit()
    conn.close()

    logger.info(
        "Migration complete. %d records inserted, %d skipped → %s",
        inserted,
        skipped,
        DB_PATH,
    )


if __name__ == "__main__":
    migrate()
