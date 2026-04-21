from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from geoalchemy2 import Geometry
from .base import Base


class Farm(Base):
    """
    SQLAlchemy model representing a farmland record in PostGIS.
    """
    __tablename__ = "farms"

    phone_number: Mapped[str] = mapped_column(String(20), primary_key=True)
    
    # PostGIS Geometry column for Polygons
    # 4326 is the SRID for WGS 84 (GPS standard)
    geom: Mapped[str] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True)
    )
    
    # Metadata and repair history
    fixes_applied: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    def __repr__(self) -> str:
        return f"<Farm(phone_number='{self.phone_number}', geom='{self.geom}')>"
