#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker &>/dev/null; then
    echo "Error: docker is not installed or not in PATH."
    exit 1
fi

if ! command -v uv &>/dev/null; then
    echo "Error: uv is not installed. See https://docs.astral.sh/uv/"
    exit 1
fi

# Compose reads .env, so it has to exist before anything starts.
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

echo "Starting PostGIS..."
docker compose up -d db

echo "Waiting for the database to accept connections..."
for _ in $(seq 1 30); do
    if docker compose exec -T db pg_isready -U user -d farmland_db &>/dev/null; then
        break
    fi
    sleep 1
done

if ! docker compose exec -T db pg_isready -U user -d farmland_db &>/dev/null; then
    echo "Error: the database did not become ready. Check 'docker compose logs db'."
    exit 1
fi

# Only ingest on a fresh database. Re-running the migration would prompt to replace
# the raw data and leave the materialized view stale until it is refreshed.
TABLE=$(docker compose exec -T db psql -U user -d farmland_db -tAc \
    "SELECT to_regclass('public.raw_farmers_data')" 2>/dev/null | tr -d '[:space:]')

if [ -z "$TABLE" ] || [ "$TABLE" = "" ]; then
    echo "Loading the spreadsheet into raw_farmers_data..."
    uv run --group scripts python scripts/migrate_to_postgres.py

    echo "Building the materialized view..."
    docker compose exec -T db psql -U user -d farmland_db < scripts/create_materialized_view.sql
else
    echo "Database already loaded. To rebuild it, run ./scripts/reset.sh first."
fi

echo "Starting the API on http://127.0.0.1:8000 (docs at /docs)"
exec uv run uvicorn src.main:app --reload --port 8000
