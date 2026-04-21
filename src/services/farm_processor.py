from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from shapely.validation import make_valid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

# ── India geographic bounds (WGS84) ──────────────────────────────────────────
_INDIA_LAT_MIN, _INDIA_LAT_MAX = 6.0, 38.0
_INDIA_LON_MIN, _INDIA_LON_MAX = 66.0, 98.0


@dataclass
class GeometryResult:
    """
    Structured result from process_farm_geometry().
    """
    is_valid: bool
    processed_geometry: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    fixes_applied: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


def _is_in_india(lon: float, lat: float) -> bool:
    """Check if a coordinate pair is within approximate India bounding box."""
    return _INDIA_LAT_MIN <= lat <= _INDIA_LAT_MAX and _INDIA_LON_MIN <= lon <= _INDIA_LON_MAX


def process_farm_geometry(
    geometry_dict: Dict[str, Any],
    fixes_applied: Optional[List[str]] = None,
) -> GeometryResult:
    """
    Processes GeoJSON geometry using Shapely with Silent Healing.

    Healing pipeline (in order):
      1. Lat/Lon Swap Detection — if coordinates appear swapped outside India's
         bounding box, they are automatically transposed.
      2. Topology Fix (buffer(0)) — untangles self-intersecting "bowtie"
         polygons while preserving the original farm shape. Falls back to
         convex_hull only if buffer(0) also fails.
      3. CRS annotation — appends EPSG:4326 metadata.

    Returns:
        GeometryResult dataclass.
    """
    if fixes_applied is None:
        fixes_applied = []

    try:
        coords = geometry_dict.get("coordinates", [[]])[0]

        # ── Fix 1: Lat/Lon Swap Detection ─────────────────────────────────────
        # In GeoJSON, order is [longitude, latitude].
        # If first coord looks like [lat, lon] (lon < 40 but lat > 60), swap.
        if coords:
            first_lon, first_lat = coords[0][0], coords[0][1]
            if not _is_in_india(first_lon, first_lat) and _is_in_india(first_lat, first_lon):
                geometry_dict = {
                    "type": geometry_dict["type"],
                    "coordinates": [[[c[1], c[0]] for c in ring] for ring in geometry_dict["coordinates"]],
                }
                fixes_applied.append("Auto-swapped Lat/Lon coordinates (were outside India bounds).")
                logger.info("Lat/Lon swap applied for farm data.")

        geom = shape(geometry_dict)

        # ── Fix 2: Topology Repair (buffer(0) preferred over convex_hull) ─────
        # buffer(0) preserves the original shape; convex_hull "overshoots"
        if not geom.is_valid:
            healed = geom.buffer(0)
            if healed.is_valid and not healed.is_empty:
                geom = healed
                fixes_applied.append("Repaired self-intersecting polygon using topology fix (buffer(0)).")
                logger.info("buffer(0) topology fix applied.")
            else:
                # Last resort fallback
                geom = geom.convex_hull
                fixes_applied.append("Repaired self-intersecting polygon using Convex Hull (fallback).")
                logger.warning("Fell back to convex_hull for geometry repair.")

        # ── Rebuild GeoJSON ────────────────────────────────────────────────────
        fixed_geometry: Dict[str, Any] = dict(mapping(geom))
        fixed_geometry["crs"] = {
            "type": "name",
            "properties": {"name": "EPSG:4326"},
        }

        status = "success_with_fixes" if fixes_applied else "success"

        return GeometryResult(
            is_valid=True,
            processed_geometry=fixed_geometry,
            status=status,
            fixes_applied=fixes_applied,
        )

    except Exception as e:
        return GeometryResult(
            is_valid=False,
            error_message=f"Geometry processing error: {str(e)}",
            fixes_applied=fixes_applied,
        )
