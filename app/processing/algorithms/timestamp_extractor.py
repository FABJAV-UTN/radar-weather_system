"""
Extracción de timestamp desde la imagen de radar (OCR).

El radar DACC escribe la fecha y hora directamente sobre la imagen.
El programa usa esa hora (no la de descarga) para nombrar el archivo.

Luego se restan 3 horas para convertir de la zona horaria del radar
a UTC-3 (hora local de Mendoza / Argentina Standard Time).

Si el OCR falla, se devuelve None y el pipeline puede decidir:
  - Usar la hora de descarga como fallback (con advertencia)
  - Descartar la imagen

Enfoque: OCR sobre imagen completa con regex flexible.
- Se realiza OCR sobre toda la imagen (convert RGB)
- Se busca fecha con regex: \\d{4}[/-]\\d{2}[/-]\\d{2}
- Se busca hora con regex: (\\d{2}):(\\d{2}):(\\d{2})
- Se combina en datetime y se aplica offset -3h
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

# Región de la imagen donde aparece el timestamp (en píxeles).
# El texto está en un banner verde en la parte superior de la imagen.
TIMESTAMP_CROP: dict[str, int] = {
    "x": 0,
    "y": 18,
    "w": 400,
    "h": 28,
}

# Patrones de timestamp posibles en la imagen del radar.
# Se prueban en orden; el primero que matchee gana.
TIMESTAMP_PATTERNS: list[tuple[str, str]] = [
    # "2026/05/07 03:40:00 UTC"  ← el formato real del DACC
    (r"(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})", "%Y/%m/%d %H:%M:%S"),
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

    Enfoque: OCR sobre imagen completa con regex flexible.
    - Lee texto completo de la imagen
    - Busca fecha: YYYY-MM-DD o YYYY/MM/DD
    - Busca hora: HH:MM:SS
    - Combina y aplica offset UTC-3

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

    # OCR sobre imagen completa (RGB)
    rgb_image = image.convert("RGB")
    raw_text = pytesseract.image_to_string(rgb_image)
    
    # Limpiar: normalizar espacios
    text = " ".join(raw_text.split())
    logger.debug("OCR raw text: %r", text)

    # Buscar fecha: YYYY-MM-DD o YYYY/MM/DD
    date_match = re.search(r"(\d{4})[/-](\d{2})[/-](\d{2})", text)
    if not date_match:
        logger.warning("No se encontró fecha en OCR")
        return None

    year = int(date_match.group(1))
    month = int(date_match.group(2))
    day = int(date_match.group(3))
    logger.debug("Fecha extraída: %04d-%02d-%02d", year, month, day)

    # Buscar hora: HH:MM:SS
    time_match = re.search(r"(\d{2}):(\d{2}):(\d{2})", text)
    if not time_match:
        logger.warning("No se encontró hora en OCR")
        return None

    hour = int(time_match.group(1))
    minute = int(time_match.group(2))
    second = int(time_match.group(3))
    logger.debug("Hora extraída: %02d:%02d:%02d", hour, minute, second)

    # Construir datetime
    try:
        dt = datetime(year, month, day, hour, minute, second)
    except ValueError as e:
        logger.error("Error creando datetime: %s", e)
        return None

    # Aplicar offset de zona horaria (UTC → Mendoza UTC-3)
    local_dt = dt + timedelta(hours=RADAR_TIMEZONE_OFFSET_HOURS)
    logger.info("Timestamp imagen (UTC): %s → local (UTC-3): %s", dt, local_dt)

    return local_dt


def ocr_image_text(image: Image.Image, psm: int = 6) -> str:
    """Extrae texto de una imagen completa usando Tesseract."""
    try:
        import pytesseract
    except ImportError:
        logger.error(
            "pytesseract no instalado. Agregá 'pytesseract' con 'uv add pytesseract'. "
            "También necesitás Tesseract instalado en el sistema."
        )
        return ""

    raw_text = pytesseract.image_to_string(image, config=f"--psm {psm}")
    return raw_text.strip()


def parse_timestamp(text: str) -> datetime | None:
    """Intenta parsear una fecha/hora a partir de texto OCR completo."""
    return _parse_timestamp(text)


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
    """
    Recorta la región donde aparece el timestamp.
    
    [DEPRECATED: Ya no se usa en extract_timestamp()]
    Mantenido por compatibilidad, pero el nuevo enfoque hace OCR sobre la imagen completa.
    """
    c = TIMESTAMP_CROP
    return image.crop((c["x"], c["y"], c["x"] + c["w"], c["y"] + c["h"]))


def _parse_timestamp(text: str) -> datetime | None:
    text = re.sub(r"[^\d/:.+ -]", "", text).strip()
    text = text.replace("+", ":").replace(";", ":").replace("ː", ":")

    match = re.search(r"(\d{4}).(\d{2}).(\d{2})\s+(\d{2}).(\d{2}).(\d{2})", text)
    if match:
        year_text = match.group(1)
        year = int(year_text)
        if year > 2100 and year_text.startswith("9"):
            year = int(year_text.replace("9", "2"))

        try:
            return datetime(
                year, int(match.group(2)), int(match.group(3)),
                int(match.group(4)), int(match.group(5)), int(match.group(6)),
            )
        except ValueError:
            pass

    for pattern, fmt in TIMESTAMP_PATTERNS:
        match = re.search(pattern, text)
        if match:
            try:
                return datetime.strptime(match.group(1), fmt)
            except ValueError:
                continue

    return None