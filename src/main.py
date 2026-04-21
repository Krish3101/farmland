from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import router as api_router
from src.services.database import engine
import uvicorn
from pathlib import Path

# Resolve paths relative to this file
_SRC_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _SRC_DIR / "static"
_INDEX_HTML = _STATIC_DIR / "index.html"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    yield
    # Shutdown logic
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
