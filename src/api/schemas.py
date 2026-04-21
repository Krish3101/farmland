from pydantic import BaseModel, Field
from typing import Optional, List


# ── Request schemas ───────────────────────────────────────────────────────────

class SentinelSubmitRequest(BaseModel):
    """POST /api/sentinel/submit request body."""
    geojson_payload: dict


# ── GeoJSON component schemas ─────────────────────────────────────────────────

class GeoJSONGeometry(BaseModel):
    type: str = "Polygon"
    coordinates: List[List[List[float]]]
    crs: Optional[dict] = None


class FeatureProperties(BaseModel):
    """
    RFC 7946 compliant: ALL custom fields live inside 'properties'.
    No custom data at the Feature root level (M-3 fix).
    """
    status: str
    kvk_number: str
    fixes_applied: List[str] = []
    error_message: Optional[str] = None
    crs: str = "EPSG:4326"


# ── Top-level response schemas ────────────────────────────────────────────────

class FarmFeatureResponse(BaseModel):
    """
    Strict RFC 7946 GeoJSON Feature response.
    Custom metadata is enclosed entirely within 'properties'.
    """
    type: str = Field(default="Feature", description="GeoJSON object type.")
    geometry: Optional[GeoJSONGeometry] = None
    properties: FeatureProperties


class ErrorResponse(BaseModel):
    """Returned when farm data cannot be retrieved or processed."""
    properties: FeatureProperties


class SentinelResponse(BaseModel):
    status: str
    message: str
