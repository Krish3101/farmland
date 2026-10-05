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

set -a
# shellcheck disable=SC1091
source .env
set +a

# Replace the KEY= line in .env (works with both GNU and macOS tools).
set_env() {
    grep -q "^$1=" .env || echo "$1=" >> .env
    awk -v k="$1" -v v="$2" 'index($0, k "=") == 1 { print k "=" v; next } { print }' .env > .env.tmp
    mv .env.tmp .env
}

DB_USER="${POSTGRES_USER:-farmland}"
DB_NAME="${POSTGRES_DB:-farmland_db}"

# Empty secrets get random values on the first run, so no default password or key is ever live.
if [ -z "${POSTGRES_PASSWORD:-}" ]; then
    POSTGRES_PASSWORD="$(openssl rand -hex 24)"
    set_env POSTGRES_PASSWORD "$POSTGRES_PASSWORD"
fi
if [ -z "${DATABASE_URL:-}" ]; then
    DATABASE_URL="postgresql+asyncpg://$DB_USER:$POSTGRES_PASSWORD@localhost:${DB_PORT:-5434}/$DB_NAME"
    set_env DATABASE_URL "$DATABASE_URL"
fi
if [ -z "${API_KEY:-}" ]; then
    API_KEY="$(openssl rand -hex 24)"
    set_env API_KEY "$API_KEY"
    echo "Generated API_KEY in .env"
fi
export POSTGRES_PASSWORD DATABASE_URL API_KEY

echo "Starting PostGIS..."
docker compose up -d db

echo "Waiting for the database to accept connections..."
for _ in $(seq 1 30); do
    if docker compose exec -T db pg_isready -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" &>/dev/null; then
        break
    fi
    sleep 1
done

if ! docker compose exec -T db pg_isready -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" &>/dev/null; then
    echo "Error: the database did not become ready. Check 'docker compose logs db'."
    exit 1
fi

# Check if the materialized view exists
VIEW=$(docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT to_regclass('public.processed_farm_geojson')" 2>/dev/null | tr -d '[:space:]')

if [ -z "$VIEW" ]; then
    echo "Loading spreadsheet into raw_farmers_data..."
    uv run --group scripts python scripts/ingest.py --force

    echo "Building the cleaning function and materialized view..."
    docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -1 < sql/clean_and_build.sql

    REJECTED=$(docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" -tAc \
        "SELECT count(*) FROM farm_rejections")
    echo "Rejected farms: $REJECTED (see the farm_rejections view)"
else
    echo "Database already loaded and processed."
fi

echo "Starting the API on http://127.0.0.1:8000 (docs at /docs)"
exec uv run uvicorn src.main:app --port 8000
