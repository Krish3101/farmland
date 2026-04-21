from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import router as api_router
import uvicorn
from pathlib import Path

# Resolve paths relative to this file so CWD never matters
_SRC_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _SRC_DIR / "static"
_INDEX_HTML = _STATIC_DIR / "index.html"

app = FastAPI(
    title="Farmland Processing Pipeline",
    description=(
        "REST API for retrieving, auto-cleaning, and geocoding farmland geometry "
        "with Silent Healing telemetry. Data is served from a pre-built SQLite "
        "database (farmland.db) via aiosqlite for non-blocking async reads."
    ),
    version="3.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files ───────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def read_index() -> FileResponse:
    return FileResponse(str(_INDEX_HTML))


# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api")


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
