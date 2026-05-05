"""
Pipeline de procesamiento de imágenes de radar.

Orquesta todos los pasos del Subsistema 1:
    GIF (fuente) → recorte → limpieza → relleno → geolocalizacion → GeoTIFF (DB)

Dos modos según la fuente:
    - DACC API / Cloud bank: recortar → limpiar → rellenar → geolocalizar (datotif1)
    - Banco local:           limpiar → rellenar → geolocalizar (datotif2 o datotif3)

Uso:
    loader = GeoReferenceLoader()
    loader.load_all()
    pipeline = RadarPipeline(geo_loader=loader)
    await pipeline.process(image_path, source_type="dacc_api")
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PIL import Image

from app.processing.algorithms.cleaner import clean_image
from app.processing.algorithms.cropper import crop_margins, detect_bank_image_type
from app.processing.algorithms.georeferencer import GeoReferenceLoader, apply_geo_reference
from app.processing.algorithms.hole_filler import fill_gaps
from app.processing.algorithms.timestamp_extractor import extract_timestamp, format_filename

logger = logging.getLogger(__name__)

# Nombre de lugar para el naming de archivos (ajustar por config si el sistema
# procesa múltiples radares en el futuro)
DEFAULT_LOCATION = "san_rafael"


class RadarPipeline:
    """
    Pipeline completo de procesamiento de radar GIF → GeoTIFF.

    Instanciar una vez y reutilizar para múltiples imágenes.
    El geo_loader debe tener cargados los datotifs antes de procesar.
    """

    def __init__(
        self,
        geo_loader: GeoReferenceLoader,
        output_dir: Path | None = None,
        location: str = DEFAULT_LOCATION,
    ):
        self.geo_loader = geo_loader
        self.output_dir = output_dir or Path("data/geotiffs")
        self.location = location
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process(
        self,
        image_path: Path,
        source_type: str,  # "dacc_api" | "local_bank" | "cloud_bank"
        fallback_timestamp: datetime | None = None,
    ) -> Path | None:
        """
        Procesa una imagen de radar y la guarda como GeoTIFF.

        Args:
            image_path: Ruta al GIF de entrada.
            source_type: De dónde viene la imagen (determina si recortar y qué datotif usar).
            fallback_timestamp: Timestamp a usar si el OCR falla. Si None y el OCR falla,
                                se descarta la imagen (devuelve None).

        Returns:
            Ruta al GeoTIFF generado, o None si falló el timestamp.
        """
        logger.info("Procesando imagen: %s (fuente: %s)", image_path.name, source_type)

        image = Image.open(image_path)

        # ─── PASO 1: Recorte de márgenes ──────────────────────────────────────
        # Sólo para imágenes del DACC o cloud bank.
        # Las del banco local ya están recortadas.
        if source_type in ("dacc_api", "cloud_bank"):
            image = crop_margins(image)
            datotif_id = 1
        else:  # local_bank
            datotif_id = detect_bank_image_type(image)

        # ─── PASO 2: Extraer timestamp (antes de limpiar para tener texto OCR) ─
        timestamp = extract_timestamp(image)
        if timestamp is None:
            if fallback_timestamp is not None:
                logger.warning(
                    "OCR falló para %s. Usando timestamp de fallback: %s",
                    image_path.name, fallback_timestamp
                )
                timestamp = fallback_timestamp
            else:
                logger.error(
                    "OCR falló y no hay fallback para %s. Imagen descartada.", image_path.name
                )
                return None

        # ─── PASO 3: Limpieza ─────────────────────────────────────────────────
        clean_rgb, gap_mask = clean_image(image)

        # ─── PASO 4: Relleno de huecos ────────────────────────────────────────
        filled_rgb = fill_gaps(clean_rgb, gap_mask)

        # ─── PASO 5: Geolocalización ──────────────────────────────────────────
        geo = self.geo_loader.get(datotif_id)

        filename = format_filename(self.location, timestamp)
        output_path = self.output_dir / f"{filename}.tif"

        apply_geo_reference(filled_rgb, geo, output_path)

        logger.info(
            "GeoTIFF guardado: %s (datotif=%d, timestamp=%s)",
            output_path.name, datotif_id, timestamp.isoformat()
        )

        return output_path