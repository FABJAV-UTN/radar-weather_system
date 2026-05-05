"""
Limpieza de imágenes de radar.

Elimina del GIF todo lo que NO es precipitación:
- Fondo negro del mapa base
- Divisiones políticas (líneas blancas/grises tenues)
- Textos y números de escala
- Marca de agua del radar DACC

Devuelve:
- La imagen limpia (sólo píxeles de tormenta, resto → (0,0,0,0) si RGBA o (0,0,0) si RGB)
- Una máscara booleana indicando dónde estaba la marca de agua (para inpainting posterior)
"""

import numpy as np
from PIL import Image

from app.processing.algorithms.dbz_colors import classify_array, DEFAULT_COLOR_THRESHOLD


# ─── Configuración de la marca de agua ────────────────────────────────────────
# Región aproximada donde aparece la marca de agua del radar DACC.
# Coordenadas en píxeles DESPUÉS del recorte de márgenes.
# Ajustá estos valores cuando tengas imágenes reales.
WATERMARK_REGION: dict[str, int] = {
    "x": 0,       # columna inicial
    "y": 0,       # fila inicial
    "w": 120,     # ancho de la región
    "h": 30,      # alto de la región
}

# Umbral de luminosidad para considerar un píxel como "fondo negro"
BACKGROUND_LUMINANCE_THRESHOLD: int = 15

# Umbral para clasificar líneas de divisiones políticas:
# píxeles gris claro que no son tormenta pero tampoco fondo negro
POLITICAL_DIVISION_THRESHOLD: int = 80


def clean_image(
    image: Image.Image,
    color_threshold: float = DEFAULT_COLOR_THRESHOLD,
    watermark_region: dict[str, int] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Limpia la imagen de radar eliminando todo lo que no es precipitación.

    Args:
        image: Imagen PIL (ya recortada).
        color_threshold: Distancia máxima en RGB para clasificar un píxel como dBZ.
        watermark_region: Región de la marca de agua. Si None, usa WATERMARK_REGION.

    Returns:
        clean_rgb: Array (H, W, 3) uint8, sólo píxeles de tormenta (resto = negro).
        watermark_mask: Array (H, W) bool, True donde había marca de agua.
    """
    wm_region = watermark_region or WATERMARK_REGION
    rgb = np.array(image.convert("RGB"), dtype=np.uint8)

    # 1. Clasificar cada píxel en su dBZ
    dbz_map = classify_array(rgb, threshold=color_threshold)  # (H, W), 0 = no es tormenta

    # 2. Máscara de tormenta (píxeles que sí clasificaron)
    storm_mask = dbz_map > 0  # (H, W) bool

    # 3. Máscara de la región de marca de agua
    watermark_mask = _build_watermark_mask(rgb.shape[:2], wm_region)

    # 4. Píxeles de tormenta dentro de la marca de agua → están "borrados"
    #    Los necesitamos recuperar en el paso de inpainting.
    #    La máscara que devolvemos indica DÓNDE hay hueco por marca de agua:
    #    es la zona watermark donde NO clasificó como tormenta (porque la marca la tapó).
    gap_mask = watermark_mask & ~storm_mask

    # 5. Construir imagen limpia: sólo los píxeles de tormenta
    clean_rgb = np.zeros_like(rgb)
    clean_rgb[storm_mask] = rgb[storm_mask]

    return clean_rgb, gap_mask


def _build_watermark_mask(shape: tuple[int, int], region: dict[str, int]) -> np.ndarray:
    """Construye máscara booleana para la región de marca de agua."""
    h, w = shape
    mask = np.zeros((h, w), dtype=bool)
    x, y = region["x"], region["y"]
    rw, rh = region["w"], region["h"]
    mask[y: y + rh, x: x + rw] = True
    return mask