from shapely.geometry import shape, mapping
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class GeometryResult:
    """
    Structured result from process_farm_geometry().
    Replaces the fragile 5-tuple return value (M-1 fix).
    """
    is_valid: bool
    processed_geometry: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    fixes_applied: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


def process_farm_geometry(
    geometry_dict: Dict[str, Any],
    fixes_applied: Optional[List[str]] = None,   # C-2 fix: safe default
) -> GeometryResult:
    """
    Processes GeoJSON geometry using Shapely.
    Silent Healing with Telemetry:
      - Repairs self-intersecting polygons via convex_hull (tracked in fixes_applied).
      - Sets status to 'success_with_fixes' when any fixes were applied.
      - Appends official CRS information.

    Args:
        geometry_dict: Raw GeoJSON geometry dict.
        fixes_applied:  List of fix strings accumulated by the caller (db_client).
                        Defaults to an empty list if None (C-2 fix).

    Returns:
        GeometryResult dataclass (M-1 fix — no more fragile 5-tuple).
    """
    # C-2 fix: handle None default safely
    if fixes_applied is None:
        fixes_applied = []

    try:
        geom = shape(geometry_dict)

        # Auto-Fix 3: Convex Hull for invalid (self-intersecting) geometry
        if not geom.is_valid:
            geom = geom.convex_hull
            fixes_applied.append("Applied Convex Hull to repair self-intersecting polygon.")

        # Rebuild GeoJSON from corrected Shapely object
        fixed_geometry: Dict[str, Any] = dict(mapping(geom))

        # Append CRS metadata (user requirement; RFC 7946 prefers implicit WGS84)
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
