import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api import router as api_router
from src.db import engine, get_db_session

load_dotenv()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.api_key = os.getenv("API_KEY")
    if not app.state.api_key:
        raise RuntimeError("API_KEY is not set. Run ./scripts/start.sh or set it in .env.")
    yield
    await engine.dispose()


app = FastAPI(
    title="Farmland",
    description="Serves cleaned farmland boundaries as GeoJSON, backed by PostGIS.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get(
    "/health",
    summary="Health check, verifies database connectivity",
    tags=["System"],
)
async def health_check(session: AsyncSession = Depends(get_db_session)):
    """
    Returns the health status of the API and its database connection.
    Verifies that the database is reachable and the processed materialized view exists.
    """
    try:
        result = await session.execute(
            text("SELECT to_regclass('processed_farm_geojson') IS NOT NULL")
        )
        view_ready = result.scalar()
        if not view_ready:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "unhealthy",
                    "database": "connected",
                    "version": app.version,
                    "error": "Database materialized view is not initialized.",
                },
            )
        return {
            "status": "healthy",
            "database": "connected",
            "version": app.version,
        }
    except Exception as exc:
        logger.error("Health check failed: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "version": app.version,
                "error": "Database connectivity check failed.",
            },
        )


app.include_router(api_router, prefix="/api")
