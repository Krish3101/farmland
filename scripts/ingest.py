import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_EXCEL_PATH = PROJECT_ROOT / "data" / "farmers_data.xls"
DEFAULT_DB_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://farmland:farmland@localhost:5434/farmland_db"
)
BUILD_SQL_PATH = PROJECT_ROOT / "sql" / "clean_and_build.sql"

# The sheet has an empty first column and two header rows; these are the ten real columns.
COLUMNS = [
    "serial_no",
    "farmer_name",
    "phone",
    "transplant_date",
    "variety",
    "address",
    "corner_a",
    "corner_b",
    "corner_c",
    "corner_d",
]


def ingest(excel_path: Path, db_url: str):
    """Load the sheet into raw_farms as typed, then rebuild the cleaning function and views."""
    if not excel_path.exists():
        logger.error("Source file not found at %s. No data was written.", excel_path)
        sys.exit(1)

    if not db_url:
        logger.error("Database URL is not provided. Set DATABASE_URL or pass --db-url.")
        sys.exit(1)

    logger.info("Reading source spreadsheet from %s ...", excel_path)
    try:
        df = pd.read_excel(
            excel_path,
            engine="xlrd",
            header=None,
            skiprows=3,
            usecols=range(1, 11),
            names=COLUMNS,
            dtype=str,
        )
    except Exception as exc:
        logger.error("Failed to parse source file '%s': %s. No data was written.", excel_path, exc)
        sys.exit(1)

    engine = create_engine(db_url)
    # One transaction: the raw table and every view are rebuilt together, or not at all.
    try:
        with engine.begin() as conn:
            # CASCADE drops the views built on the old table; the SQL file recreates them.
            conn.execute(text("DROP TABLE IF EXISTS raw_farms CASCADE"))
            df.to_sql(name="raw_farms", con=conn, index=False)
            conn.exec_driver_sql(BUILD_SQL_PATH.read_text())
            built = conn.execute(text("SELECT count(*) FROM farms")).scalar()
            rejected = conn.execute(text("SELECT count(*) FROM farm_rejections")).scalar()
    except Exception as exc:
        logger.error("Failed to load and build: %s. Nothing was changed.", exc)
        sys.exit(1)

    print(f"{built} farms built, {rejected} rejected")


def main():
    parser = argparse.ArgumentParser(
        description="Load the farmland spreadsheet and build the cleaned farm views."
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
    args = parser.parse_args()
    ingest(excel_path=args.file, db_url=args.db_url)


if __name__ == "__main__":
    main()
