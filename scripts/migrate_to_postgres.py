import os
import sys
import logging
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# Load environment variables
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

EXCEL_PATH = PROJECT_ROOT / "src" / "data" / "farmers_data.xls"


def migrate(force: bool = False):
    # Sync database URL for pandas
    async_db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/farmland_db")
    sync_db_url = async_db_url.replace("+asyncpg", "+psycopg2")
    if sync_db_url.startswith("postgresql://"):
        # Ensure it uses psycopg2 explicitly or fallback to default
        pass
    
    engine = create_engine(sync_db_url)

    # Safety check — warn if the table already exists (avoid accidental overwrites)
    inspector = inspect(engine)
    if inspector.has_table("raw_farmers_data") and not force:
        logger.warning(
            "Table 'raw_farmers_data' already exists. "
            "This will DROP and RECREATE the table, potentially orphaning the materialized view. "
            "Run with --force to confirm, or refresh the materialized view afterwards."
        )
        confirm = input("Proceed? [y/N]: ").strip().lower()
        if confirm != "y":
            logger.info("Migration aborted.")
            return

    if not EXCEL_PATH.exists():
        logger.error("Excel file not found at %s", EXCEL_PATH)
        return

    logger.info("Reading %s ...", EXCEL_PATH)
    try:
        df = pd.read_excel(EXCEL_PATH, engine="xlrd")
    except Exception as exc:
        logger.error("Failed to read Excel file: %s", exc)
        return

    logger.info("Read %d rows, %d columns.", len(df), len(df.columns))

    # Ingest the dataframe to PostgreSQL table
    logger.info("Dumping dataframe to 'raw_farmers_data' table...")
    df.to_sql(name="raw_farmers_data", con=engine, if_exists="replace", index=False)
    
    logger.info("Migration to raw_farmers_data complete.")
    logger.info(
        "REMINDER: If the materialized view exists, refresh it with:\n"
        "  PGPASSWORD=password psql -h localhost -U user -d farmland_db "
        "-c 'REFRESH MATERIALIZED VIEW CONCURRENTLY processed_farm_geojson;'"
    )


if __name__ == "__main__":
    force_flag = "--force" in sys.argv
    migrate(force=force_flag)
