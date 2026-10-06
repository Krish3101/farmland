import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_EXCEL_PATH = PROJECT_ROOT / "data" / "farmers_data.xls"
DEFAULT_DB_URL = os.getenv("DATABASE_URL")


def get_sync_db_url(url: str) -> str:
    """Ensure database URL uses psycopg2 driver for synchronous pandas operations."""
    if "+asyncpg" in url:
        return url.replace("+asyncpg", "+psycopg2")
    if url.startswith("postgresql://") and "+psycopg2" not in url:
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def ingest(excel_path: Path, db_url: str, force: bool = False):
    """
    Ingests source spreadsheet records into the raw_farmers_data PostgreSQL table.

    Preserves source structure as-is. If the table already exists, requires operator
    confirmation (or --force). When dependent objects like materialized views exist,
    truncates and appends in a transaction, then concurrently refreshes the materialized view.
    """
    if not excel_path.exists():
        logger.error("Source file not found at %s. No data was written.", excel_path)
        sys.exit(1)

    if not db_url:
        logger.error("Database URL is not provided. Set DATABASE_URL in .env or pass --db-url.")
        sys.exit(1)

    logger.info("Reading source spreadsheet from %s ...", excel_path)
    try:
        df = pd.read_excel(excel_path, engine="xlrd")
    except Exception as exc:
        logger.error("Failed to parse source file '%s': %s. No data was written.", excel_path, exc)
        sys.exit(1)

    rows_count, cols_count = len(df), len(df.columns)
    logger.info("Successfully read %d rows and %d columns.", rows_count, cols_count)

    sync_url = get_sync_db_url(db_url)
    engine = create_engine(sync_url)

    try:
        inspector = inspect(engine)
        table_exists = inspector.has_table("raw_farmers_data")
    except Exception as exc:
        logger.error("Could not connect to database: %s", exc)
        sys.exit(1)

    if table_exists and not force:
        logger.warning(
            "Table 'raw_farmers_data' already exists. Ingestion will replace the raw data."
        )
        try:
            confirm = input("Proceed with replacement? [y/N]: ").strip().lower()
        except EOFError:
            confirm = "n"
        if confirm != "y":
            logger.info("Ingestion aborted by operator. Raw data left untouched.")
            return

    logger.info("Writing raw records to 'raw_farmers_data' table...")
    try:
        with engine.begin() as conn:
            if table_exists:
                conn.execute(text("TRUNCATE TABLE raw_farmers_data;"))
                df.to_sql(name="raw_farmers_data", con=conn, if_exists="append", index=False)
            else:
                df.to_sql(name="raw_farmers_data", con=conn, if_exists="replace", index=False)
    except Exception as exc:
        logger.error("Failed to write data to 'raw_farmers_data': %s", exc)
        sys.exit(1)

    logger.info("Ingestion to raw_farmers_data complete.")

    # Refresh materialized view if it exists
    autocommit_engine = engine.execution_options(isolation_level="AUTOCOMMIT")
    with autocommit_engine.connect() as conn:
        has_matview = conn.execute(
            text("SELECT to_regclass('public.processed_farm_geojson') IS NOT NULL;")
        ).scalar()
        if has_matview:
            logger.info("Refreshing materialized view 'processed_farm_geojson'...")
            try:
                conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY processed_farm_geojson;"))
            except Exception as e:
                logger.error("Failed to refresh the materialized view: %s", e)
                sys.exit(1)
            rejections_count = conn.execute(text("SELECT count(*) FROM farm_rejections;")).scalar()
            logger.info(
                "Materialized view refreshed successfully (%d rejected records).",
                rejections_count or 0,
            )


def main():
    parser = argparse.ArgumentParser(
        description="Load source farmland spreadsheet into raw PostgreSQL storage."
    )
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        default=DEFAULT_EXCEL_PATH,
        help=f"Path to source Excel file (default: {DEFAULT_EXCEL_PATH})",
    )
    parser.add_argument(
        "-d",
        "--db-url",
        type=str,
        default=DEFAULT_DB_URL,
        help="Database connection URL (default: from DATABASE_URL env)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass interactive confirmation when raw_farmers_data table already exists",
    )
    args = parser.parse_args()
    ingest(excel_path=args.file, db_url=args.db_url, force=args.force)


if __name__ == "__main__":
    main()
