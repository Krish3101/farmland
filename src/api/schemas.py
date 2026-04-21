from pydantic import BaseModel, Field
from typing import Optional, List, Union, Any


# ── GeoJSON component schemas ─────────────────────────────────────────────────

class GeoJSONGeometry(BaseModel):
    """
    Supports both Polygon and MultiPolygon to handle fragmented farm parcels.
    """
    type: str  # "Polygon" or "MultiPolygon"
    coordinates: Any  # Flexible: handles both polygon and multi-polygon coordinate arrays
    crs: Optional[dict] = None


class FeatureProperties(BaseModel):
    """
    RFC 7946 compliant: ALL custom fields live inside 'properties'.
    No custom data at the Feature root level.
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


# ── Forwarding schemas ────────────────────────────────────────────────────────

class ProcessAndForwardRequest(BaseModel):
    """Request body for POST /api/process_and_forward."""
    phone_number: str = Field(..., description="Farmer's phone number to process.")
    target_url: str = Field(..., description="Target URL to forward the GeoJSON Feature to.")


class ForwardResponse(BaseModel):
    """Response for POST /api/process_and_forward."""
    status: str
    message: str
    target_url: str
    forwarded_payload: Optional[FarmFeatureResponse] = None
