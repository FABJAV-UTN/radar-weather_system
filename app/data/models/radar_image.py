"""
Modelo de base de datos para imágenes de radar procesadas.

Guarda los metadatos del GeoTIFF generado. El archivo físico
vive en disco (GEOTIFF_STORAGE_PATH). La DB sólo guarda el path
y los metadatos para búsqueda y consulta.

Cuando migres al data bank: cambiás GEOTIFF_STORAGE_PATH en .env,
movés los archivos, y los paths relativos en la DB siguen siendo válidos
si usás rutas relativas a ese root.
"""

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Integer, String, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.data.database import Base


class RadarImage(Base):
    __tablename__ = "radar_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Identificación
    location: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Path relativo al GEOTIFF_STORAGE_PATH del .env
    # Ej: "san_rafael_040526_203000.tif"
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)

    # Timestamp de la imagen (extraído por OCR, en hora local Mendoza UTC-3)
    image_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # Fuente de la imagen
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # "dacc_api" | "local_bank" | "cloud_bank"

    # Datotif usado para la geolocalización (1, 2 o 3)
    datotif_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Extensión geográfica del GeoTIFF (bounding box como polígono PostGIS)
    # Permite queries espaciales: "dame todas las imágenes que cubren este punto"
    extent: Mapped[str | None] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326),
        nullable=True,
    )

    # Metadatos de la imagen
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Estadísticas de precipitación (para consultas rápidas sin abrir el TIF)
    max_dbz: Mapped[float | None] = mapped_column(Float, nullable=True)
    storm_pixel_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timestamps de auditoría
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<RadarImage {self.filename} @ {self.image_timestamp}>"