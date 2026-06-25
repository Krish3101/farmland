import os
import sys
import json
import logging
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import router as api_router
from src.services.database import engine, get_db_session
import uvicorn
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text

# Load environment variables
load_dotenv()

# ── Logging setup ─────────────────────────────────────────────────────────────
class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
log_handler = logging.StreamHandler(sys.stdout)
log_handler.setFormatter(JSONFormatter(datefmt="%Y-%m-%d %H:%M:%S"))

root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
for h in root_logger.handlers[:]:
    root_logger.removeHandler(h)
root_logger.addHandler(log_handler)

logger = logging.getLogger(__name__)

# Resolve paths relative to this file
_SRC_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _SRC_DIR / "static"
_INDEX_HTML = _STATIC_DIR / "index.html"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Farmland Processing Pipeline starting up...")
    yield
    # Shutdown logic
    logger.info("Shutting down — disposing database engine...")
    await engine.dispose()

app = FastAPI(
    title="Farmland Processing Pipeline",
    description=(
        "REST API for retrieving, auto-cleaning, and geocoding farmland geometry. "
        "Powered by PostgreSQL/PostGIS and SQLAlchemy."
    ),
    version="4.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_raw:
    allowed_origins = [origin.strip() for origin in allowed_origins_raw.split(",") if origin.strip()]
else:
    # Safe default: only localhost for security
    allowed_origins = ["http://localhost:3000", "http://localhost:8000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files ───────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def read_index() -> FileResponse:
    return FileResponse(str(_INDEX_HTML))


# ── Health check ──────────────────────────────────────────────────────────────
@app.get(
    "/health",
    summary="Health check — verifies database connectivity",
    tags=["System"],
)
async def health_check(session: AsyncSession = Depends(get_db_session)):
    """
    Returns the health status of the API and its database connection.
    Use this endpoint for monitoring, load balancer probes, or Docker healthchecks.
    """
    try:
        await session.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "version": app.version,
        }
    except Exception as exc:
        logger.error(f"Health check failed: {exc}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "version": app.version,
            "error": str(exc),
        }


# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api")


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
