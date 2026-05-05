"""
Pipeline de procesamiento de imágenes de radar.

Orquesta todos los pasos del Subsistema 1:
    GIF (fuente) → limpieza → relleno → geolocalización → GeoTIFF → DB

El banco local no usa subcarpetas ni distinciones artificiales entre small/large.
Las imágenes locales se procesan como "local_bank" y se clasifican por tamaño real.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.data.repositories.radar_image_repository import RadarImageRepository
from app.processing.algorithms.cleaner import clean_image
from app.processing.algorithms.cropper import crop_margins, detect_bank_image_type
from app.processing.algorithms.georeferencer import GeoReferenceLoader, apply_geo_reference
from app.processing.algorithms.hole_filler import fill_gaps
from app.processing.algorithms.timestamp_extractor import extract_timestamp, format_filename
from app.processing.services.local_source import extract_timestamp_from_filename

logger = logging.getLogger(__name__)

DEFAULT_LOCATION = "san_rafael"


class RadarPipeline:
    """
    Pipeline completo de procesamiento de radar GIF → GeoTIFF → DB.
    Instanciar una vez y reutilizar para múltiples imágenes.
    """

    def __init__(
        self,
        geo_loader: GeoReferenceLoader,
        session: AsyncSession,
        output_dir: Path | None = None,
        location: str = DEFAULT_LOCATION,
    ):
        self.geo_loader = geo_loader
        self.session = session
        self.output_dir = output_dir or Path(settings.geotiff_storage_path)
        self.location = location
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._repo = RadarImageRepository(session)

    async def process(
        self,
        image_path: Path,
        source_type: str,
        fallback_timestamp: datetime | None = None,
    ) -> Path | None:
        """
        Procesa una imagen de radar y la persiste como GeoTIFF + registro en DB.

        Args:
            image_path: Ruta al GIF de entrada.
            source_type: "dacc_api" | "local_bank" | "cloud_bank"
            fallback_timestamp: Usar si el OCR y el fallback de filename fallan. None = descartar imagen.

        Returns:
            Ruta al GeoTIFF generado, o None si falló.
        """
        logger.info("Procesando: %s (fuente: %s)", image_path.name, source_type)

        image = Image.open(image_path)

        if source_type in ("dacc_api", "cloud_bank"):
            image = crop_margins(image)
            datotif_id = 1
        elif source_type == "local_bank":
            datotif_id = detect_bank_image_type(image)
        else:
            raise ValueError(f"source_type desconocido: {source_type!r}")

        # ─── PASO 2: Extraer timestamp por OCR ────────────────────────────────
        timestamp = extract_timestamp(image)
        if timestamp is None:
            filename_timestamp = extract_timestamp_from_filename(image_path.name)
            if filename_timestamp is not None:
                logger.warning(
                    "OCR falló para %s. Usando timestamp del nombre: %s",
                    image_path.name,
                    filename_timestamp,
                )
                timestamp = filename_timestamp
            elif fallback_timestamp is not None:
                logger.warning(
                    "OCR falló para %s. Usando fallback proporcionado: %s",
                    image_path.name,
                    fallback_timestamp,
                )
                timestamp = fallback_timestamp
            else:
                logger.error("OCR falló sin fallback. Imagen descartada: %s", image_path.name)
                return None

        # ─── Verificar duplicado ──────────────────────────────────────────────
        filename = format_filename(self.location, timestamp) + ".tif"
        if await self._repo.exists(filename):
            logger.info("Ya existe en DB: %s. Salteando.", filename)
            return self.output_dir / filename

        # ─── PASO 3: Limpieza ─────────────────────────────────────────────────
        clean_rgb, gap_mask = clean_image(image)

        # ─── PASO 4: Relleno de huecos ────────────────────────────────────────
        filled_rgb = fill_gaps(clean_rgb, gap_mask)

        # ─── PASO 5: Geolocalización → GeoTIFF en disco ───────────────────────
        geo = self.geo_loader.get(datotif_id)
        output_path = self.output_dir / filename
        apply_geo_reference(filled_rgb, geo, output_path)

        # ─── PASO 6: Persistir en DB ──────────────────────────────────────────
        await self._repo.save(
            geotiff_path=output_path,
            location=self.location,
            image_timestamp=timestamp,
            source_type=source_type,
            datotif_id=datotif_id,
            storage_root=self.output_dir,
        )
        await self.session.commit()

        logger.info("Guardado: %s", output_path.name)
        return output_path


