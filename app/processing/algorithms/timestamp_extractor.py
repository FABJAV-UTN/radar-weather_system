"""
Extracción de timestamp desde la imagen de radar (OCR).

El radar DACC escribe la fecha y hora directamente sobre la imagen.
El programa usa esa hora (no la de descarga) para nombrar el archivo.

Luego se restan 3 horas para convertir de la zona horaria del radar
a UTC-3 (hora local de Mendoza / Argentina Standard Time).

Si el OCR falla, se devuelve None y el pipeline puede decidir:
  - Usar la hora de descarga como fallback (con advertencia)
  - Descartar la imagen

Formato esperado en la imagen: "DD/MM/YYYY HH:MM" o similar.
Ajustar TIMESTAMP_PATTERN cuando se confirme el formato real.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

# Offset en horas entre la hora del radar y UTC-3 (hora local Mendoza)
RADAR_TIMEZONE_OFFSET_HOURS: int = -3

# Región de la imagen donde aparece el timestamp (en píxeles, post-recorte).
# Ajustar cuando se tengan imágenes reales para calibrar.
TIMESTAMP_CROP: dict[str, int] = {
    "x": 0,
    "y": 0,
    "w": 200,
    "h": 30,
}

# Patrones de timestamp posibles en la imagen del radar.
# Se prueban en orden; el primero que matchee gana.
TIMESTAMP_PATTERNS: list[tuple[str, str]] = [
    # "04/05/2026 20:30"
    (r"(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})", "%d/%m/%Y %H:%M"),
    # "2026-05-04 20:30"
    (r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", "%Y-%m-%d %H:%M"),
    # "04-05-26 20:30"
    (r"(\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2})", "%d-%m-%y %H:%M"),
]


def extract_timestamp(image: Image.Image) -> datetime | None:
    """
    Extrae el timestamp de la imagen de radar y lo convierte a hora local.

    Args:
        image: Imagen PIL (post-recorte de márgenes).

    Returns:
        datetime en UTC-3 (hora Mendoza), o None si el OCR falló.
    """
    try:
        import pytesseract
    except ImportError:
        logger.error(
            "pytesseract no instalado. Agregá 'pytesseract' con 'uv add pytesseract'. "
            "También necesitás Tesseract instalado en el sistema."
        )
        return None

    # Recortar la región del timestamp
    crop = _crop_timestamp_region(image)

    # OCR
    raw_text = pytesseract.image_to_string(crop, config="--psm 7 digits")
    raw_text = raw_text.strip()
    logger.debug("OCR raw timestamp: %r", raw_text)

    # Parsear
    dt = _parse_timestamp(raw_text)
    if dt is None:
        logger.warning("No se pudo parsear timestamp: %r", raw_text)
        return None

    # Aplicar offset de zona horaria
    local_dt = dt + timedelta(hours=RADAR_TIMEZONE_OFFSET_HOURS)
    logger.debug("Timestamp imagen: %s → local: %s", dt, local_dt)

    return local_dt


def format_filename(location: str, timestamp: datetime) -> str:
    """
    Genera el nombre de archivo en formato lugar_ddmmaa_hhmmss.

    Args:
        location: Nombre del lugar (ej: "san_rafael").
        timestamp: Datetime en hora local.

    Returns:
        str: Ej: "san_rafael_040526_203000"
    """
    return f"{location}_{timestamp.strftime('%d%m%y_%H%M%S')}"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _crop_timestamp_region(image: Image.Image) -> Image.Image:
    """Recorta la región donde aparece el timestamp."""
    c = TIMESTAMP_CROP
    return image.crop((c["x"], c["y"], c["x"] + c["w"], c["y"] + c["h"]))


def _parse_timestamp(text: str) -> datetime | None:
    """Intenta parsear el texto con los patrones conocidos."""
    # Limpiar caracteres raros del OCR
    text = re.sub(r"[^\d/:. -]", "", text).strip()

    for pattern, fmt in TIMESTAMP_PATTERNS:
        match = re.search(pattern, text)
        if match:
            try:
                return datetime.strptime(match.group(1), fmt)
            except ValueError:
                continue

    return None