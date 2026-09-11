#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "This removes the PostGIS volume. All ingested data will be lost."
read -r -p "Continue? [y/N]: " confirm
confirm=$(printf '%s' "$confirm" | tr '[:upper:]' '[:lower:]')
if [ "$confirm" != "y" ]; then
    echo "Nothing was changed."
    exit 0
fi

echo "Stopping containers and removing the database volume..."
docker compose down -v

rm -rf .venv .pytest_cache .ruff_cache
find . -type d -name __pycache__ -not -path "./.venv/*" -prune -exec rm -rf {} + 2>/dev/null || true
echo "Virtual environment and caches cleaned"

echo "Reset complete. Run ./scripts/start.sh to rebuild from the spreadsheet."
