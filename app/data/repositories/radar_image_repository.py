"""
Repositorio para RadarImage.

Encapsula todas las operaciones de base de datos.
El pipeline no toca SQLAlchemy directamente — usa este repositorio.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from shapely.geometry import box
from geoalchemy2.shape import from_shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.models.radar_image import RadarImage


class RadarImageRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(
        self,
        geotiff_path: Path,
        location: str,
        image_timestamp: datetime,
        source_type: str,
        datotif_id: int,
        storage_root: Path,
    ) -> RadarImage:
        """
        Guarda los metadatos de un GeoTIFF recién generado en la DB.

        Args:
            geotiff_path: Path absoluto al archivo .tif en disco.
            location: Nombre del lugar (ej: "san_rafael").
            image_timestamp: Timestamp de la imagen (UTC-3, extraído por OCR).
            source_type: "dacc_api" | "local_bank" | "cloud_bank".
            datotif_id: 1, 2 o 3.
            storage_root: Root del storage (GEOTIFF_STORAGE_PATH).
                          El path guardado en DB es relativo a este root.

        Returns:
            Instancia de RadarImage persistida.
        """
        # Path relativo para portabilidad al migrar al data bank
        relative_path = str(geotiff_path.relative_to(storage_root))

        # Extraer metadatos del GeoTIFF
        meta = _extract_geotiff_metadata(geotiff_path)

        record = RadarImage(
            location=location,
            filename=geotiff_path.name,
            file_path=relative_path,
            image_timestamp=image_timestamp,
            source_type=source_type,
            datotif_id=datotif_id,
            extent=meta["extent"],
            width_px=meta["width"],
            height_px=meta["height"],
            max_dbz=meta["max_dbz"],
            storm_pixel_count=meta["storm_pixel_count"],
        )

        self._session.add(record)
        await self._session.flush()  # obtener el ID sin commitear todavía
        return record

    async def get_by_timestamp(
        self,
        location: str,
        timestamp: datetime,
    ) -> RadarImage | None:
        """Busca una imagen por ubicación y timestamp exacto."""
        stmt = select(RadarImage).where(
            RadarImage.location == location,
            RadarImage.image_timestamp == timestamp,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists(self, filename: str) -> bool:
        """Verifica si ya existe un registro con ese nombre de archivo."""
        stmt = select(RadarImage.id).where(RadarImage.filename == filename)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_by_location(
        self,
        location: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 100,
    ) -> list[RadarImage]:
        """Lista imágenes de una ubicación, opcionalmente filtradas por rango de fechas."""
        stmt = (
            select(RadarImage)
            .where(RadarImage.location == location)
            .order_by(RadarImage.image_timestamp.desc())
            .limit(limit)
        )
        if date_from:
            stmt = stmt.where(RadarImage.image_timestamp >= date_from)
        if date_to:
            stmt = stmt.where(RadarImage.image_timestamp <= date_to)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())


# ─── Helper: extraer metadatos del GeoTIFF ────────────────────────────────────

def _extract_geotiff_metadata(path: Path) -> dict:
    """
    Lee el GeoTIFF y extrae metadatos para guardar en la DB.
    Operación de lectura pura, no modifica el archivo.
    """
    with rasterio.open(path) as src:
        width = src.width
        height = src.height

        # Bounding box en WGS84 (EPSG:4326) para el extent PostGIS
        bounds = src.bounds
        try:
            bounds_wgs84 = transform_bounds(src.crs, "EPSG:4326", *bounds)
            extent_polygon = from_shape(box(*bounds_wgs84), srid=4326)
        except Exception:
            extent_polygon = None

        # Estadísticas de precipitación
        # La banda 1 (R) tiene la info de color — cualquier píxel no negro = tormenta
        band_r = src.read(1)
        band_g = src.read(2)
        band_b = src.read(3)

        storm_mask = (band_r > 0) | (band_g > 0) | (band_b > 0)
        storm_pixel_count = int(storm_mask.sum())

        # max_dbz: aproximación por color dominante
        # En el futuro esto puede mejorarse con el mapa dBZ→color
        max_dbz = _estimate_max_dbz(band_r, band_g, band_b, storm_mask)

    return {
        "width": width,
        "height": height,
        "extent": extent_polygon,
        "storm_pixel_count": storm_pixel_count,
        "max_dbz": max_dbz,
    }


def _estimate_max_dbz(
    band_r: np.ndarray,
    band_g: np.ndarray,
    band_b: np.ndarray,
    storm_mask: np.ndarray,
) -> float | None:
    """
    Estima el dBZ máximo presente en la imagen.
    Importa el clasificador para no duplicar la lógica de colores.
    """
    if not storm_mask.any():
        return None

    from app.processing.algorithms.dbz_colors import classify_array

    # Construir array RGB sólo con píxeles de tormenta para ser eficiente
    rgb = np.stack([band_r, band_g, band_b], axis=2)
    dbz_map = classify_array(rgb)

    max_val = int(dbz_map.max())
    return float(max_val) if max_val > 0 else None