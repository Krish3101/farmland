import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://farmland:farmland@localhost:5434/farmland_db"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    engine.dispose()


app = FastAPI(
    title="Farmland",
    description="Serves cleaned farmland boundaries as GeoJSON, backed by PostGIS.",
    version="0.1.0",
    lifespan=lifespan,
)


def get_db() -> Any:
    with SessionLocal() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]


class FarmProperties(BaseModel):
    farm_id: str = Field(description="Unique phone number identifying the farm.")
    area_m2: float = Field(
        description="Area of the farm polygon in square metres, measured on the spheroid."
    )


class FarmFeature(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = Field(default="Feature", description="GeoJSON Feature type.")
    geometry: dict[str, Any] = Field(
        description="Polygon geometry in WGS84 coordinate reference system."
    )
    properties: FarmProperties


class FarmFeatureCollection(BaseModel):
    type: str = Field(default="FeatureCollection", description="GeoJSON FeatureCollection type.")
    features: list[FarmFeature] = Field(description="List of valid GeoJSON farm features.")


class FarmRejection(BaseModel):
    farm_id: str = Field(description="Farm phone number or row identifier.")
    reject_reason: str = Field(description="Explanation of why the farm was rejected.")


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str


def to_feature(farm_id: str, area_m2: float | int, geojson: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": geojson,
        "properties": {"farm_id": farm_id, "area_m2": float(area_m2)},
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Database reachable and the farms view built",
    tags=["System"],
)
def health_check(session: DbSession):
    try:
        view_ready = session.execute(text("SELECT to_regclass('farms') IS NOT NULL")).scalar()
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


@app.get(
    "/api/farms",
    response_model=FarmFeatureCollection,
    summary="All valid farms as a GeoJSON FeatureCollection",
    tags=["Farmland"],
)
def list_farms(
    session: DbSession,
    limit: Annotated[
        int, Query(ge=1, le=1000, description="Maximum number of farms to return.")
    ] = 100,
    offset: Annotated[int, Query(ge=0, description="Number of farms to skip.")] = 0,
):
    rows = session.execute(
        text(
            "SELECT farm_id, area_m2, geojson FROM farms "
            "ORDER BY farm_id LIMIT :limit OFFSET :offset"
        ),
        {"limit": limit, "offset": offset},
    ).all()
    return {"type": "FeatureCollection", "features": [to_feature(*row) for row in rows]}


@app.get(
    "/api/farms/{farm_id}",
    response_model=FarmFeature,
    summary="One farm as a GeoJSON Feature",
    tags=["Farmland"],
)
def get_farm(
    farm_id: Annotated[
        str,
        Path(max_length=64, pattern=r"^[^\x00]*$", examples=["8805508334"]),
    ],
    session: DbSession,
):
    # Postgres text can't hold a NUL byte; reject it here instead of failing the query.
    row = session.execute(
        text("SELECT farm_id, area_m2, geojson FROM farms WHERE farm_id = :id"),
        {"id": farm_id},
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No farm with id {farm_id}")
    return to_feature(*row)


@app.get(
    "/api/rejections",
    response_model=list[FarmRejection],
    summary="Farms that were left out, with the reason",
    tags=["Farmland"],
)
def list_rejections(session: DbSession):
    rows = session.execute(
        text("SELECT farm_id, reject_reason FROM farm_rejections ORDER BY farm_id")
    ).all()
    return [{"farm_id": farm_id, "reject_reason": reason} for farm_id, reason in rows]
