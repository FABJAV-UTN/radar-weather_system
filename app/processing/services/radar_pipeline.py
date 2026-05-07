"""
Pipeline de procesamiento de imágenes de radar.

Orquesta todos los pasos del Subsistema 1:
    GIF (fuente) → limpieza → relleno → geolocalización → GeoTIFF → DB

Dos flujos independientes:
  • DACC: OCR con extracción de timestamp, crop, geoloc con datotif_id=1, carpetas dinámicas YYYY/MM
  • Local: timestamp de nombre de archivo, sin crop, geoloc por tamaño (detect_bank_image_type)
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
    Pipeline de procesamiento de radar GIF → GeoTIFF → DB.
    Mantiene dos flujos explícitos: DACC y Local.
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

    async def process_dacc(self, image_path: Path) -> Path | None:
        """
        Flujo DACC: OCR → timestamp - 3 horas → crop → limpieza → relleno → geoloc → GeoTIFF.

        Pasos:
          1. Recorta márgenes
          2. Extrae timestamp por OCR (con offset -3 horas)
          3. Verifica duplicado
          4. Almacena en carpetas dinámicas: dacc_api/YYYY/MM/
          5. Limpia imagen
          6. Rellena huecos
          7. Geolocalización con datotif_id=1
          8. Persiste en DB

        Args:
            image_path: Ruta al GIF de entrada.

        Returns:
            Ruta al GeoTIFF generado, o None si falló.
        """
        logger.info("DACC: Procesando %s", image_path.name)

        image = Image.open(image_path)

        # ─── PASO 1: Recorte de márgenes ─────────────────────────────────────
        image = crop_margins(image)
        datotif_id = 1

        # ─── PASO 2: Extracción de timestamp por OCR (se aplica -3 horas) ─────
        timestamp = extract_timestamp(image)
        if timestamp is None:
            logger.error("DACC: OCR falló. Imagen descartada: %s", image_path.name)
            return None

        # ─── PASO 3: Verificar duplicado ─────────────────────────────────────
        filename = format_filename(self.location, timestamp) + ".tif"
        if await self._repo.get_by_timestamp(self.location, timestamp) is not None:
            logger.info(
                "DACC: Duplicado detectado para %s @ %s. Salteando.",
                self.location,
                timestamp,
            )
            return None

        # ─── PASO 4: Almacenamiento dinámico dacc_api/YYYY/MM ────────────────
        output_root = (
            self.output_dir
            / "dacc_api"
            / timestamp.strftime("%Y")
            / timestamp.strftime("%m")
        )
        output_root.mkdir(parents=True, exist_ok=True)

        # ─── PASO 5: Limpieza ────────────────────────────────────────────────
        clean_rgb, gap_mask = clean_image(image)

        # ─── PASO 6: Relleno de huecos ───────────────────────────────────────
        filled_rgb = fill_gaps(clean_rgb, gap_mask)

        # ─── PASO 7: Geolocalización → GeoTIFF en disco ──────────────────────
        geo = self.geo_loader.get(datotif_id)
        output_path = output_root / filename
        apply_geo_reference(filled_rgb, geo, output_path)

        # ─── PASO 8: Persistir en DB ────────────────────────────────────────
        await self._repo.save(
            geotiff_path=output_path,
            location=self.location,
            image_timestamp=timestamp,
            source_type="dacc_api",
            datotif_id=datotif_id,
            storage_root=self.output_dir,
        )
        await self.session.commit()

        logger.info("DACC: Guardado: %s", output_path.name)
        return output_path

    async def process_local(self, image_path: Path) -> Path | None:
        """
        Flujo Local: timestamp de filename → limpieza → relleno → geoloc por tamaño → GeoTIFF.

        Pasos:
          1. Abre imagen (sin crop)
          2. Extrae timestamp del nombre de archivo (sin OCR, sin offset)
          3. Verifica duplicado
          4. Almacena en carpeta raíz (sin subcarpetas dinámicas)
          5. Limpia imagen
          6. Rellena huecos
          7. Geolocalización según tamaño (detect_bank_image_type)
          8. Persiste en DB

        Args:
            image_path: Ruta al GIF de entrada.

        Returns:
            Ruta al GeoTIFF generado, o None si falló.
        """
        logger.info("Local: Procesando %s", image_path.name)

        image = Image.open(image_path)

        # ─── PASO 1: Sin crop, detección de tipo por tamaño ──────────────────
        datotif_id = detect_bank_image_type(image)

        # ─── PASO 2: Extracción de timestamp del nombre de archivo ───────────
        timestamp = extract_timestamp_from_filename(image_path.name)
        if timestamp is None:
            logger.error(
                "Local: No se pudo extraer timestamp del nombre. Imagen descartada: %s",
                image_path.name,
            )
            return None

        # ─── PASO 3: Verificar duplicado ─────────────────────────────────────
        filename = format_filename(self.location, timestamp) + ".tif"
        if await self._repo.get_by_timestamp(self.location, timestamp) is not None:
            logger.info(
                "Local: Duplicado detectado para %s @ %s. Salteando.",
                self.location,
                timestamp,
            )
            return None

        # ─── PASO 4: Almacenamiento en carpeta raíz ──────────────────────────
        output_root = self.output_dir
        output_root.mkdir(parents=True, exist_ok=True)

        # ─── PASO 5: Limpieza ────────────────────────────────────────────────
        clean_rgb, gap_mask = clean_image(image)

        # ─── PASO 6: Relleno de huecos ───────────────────────────────────────
        filled_rgb = fill_gaps(clean_rgb, gap_mask)

        # ─── PASO 7: Geolocalización → GeoTIFF en disco ──────────────────────
        geo = self.geo_loader.get(datotif_id)
        output_path = output_root / filename
        apply_geo_reference(filled_rgb, geo, output_path)

        # ─── PASO 8: Persistir en DB ────────────────────────────────────────
        await self._repo.save(
            geotiff_path=output_path,
            location=self.location,
            image_timestamp=timestamp,
            source_type="local_bank",
            datotif_id=datotif_id,
            storage_root=self.output_dir,
        )
        await self.session.commit()

        logger.info("Local: Guardado: %s", output_path.name)
        return output_path


