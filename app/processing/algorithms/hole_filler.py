"""
Relleno de huecos en imagen de radar (inpainting).

Problema original: el método de "20 pasadas + vecinos 4-dir" expande
y deforma la tormenta porque no distingue entre:
  - Hueco REAL: píxel vacío *dentro* de una zona de tormenta continua
  - Borde de tormenta: píxel vacío en la periferia, que debe permanecer vacío

Solución implementada: inpainting conservador en 2 fases.

FASE 1 — Relleno por zona de hueco conocida (marca de agua):
  Se conoce exactamente qué región fue tapada. Dentro de esa región,
  se rellenan los huecos propagando el color del vecino más frecuente
  de entre los píxeles de tormenta adyacentes.
  → Sin iteraciones infinitas, sin expansión fuera de la máscara.

FASE 2 — Relleno de huecos internos generales (opcional):
  Para pequeños agujeros internos (no relacionados con la marca de agua)
  se usa binary_fill_holes de scipy, que sólo rellena cavidades
  completamente rodeadas por tormenta. No toca los bordes.
  → Cero deformación garantizada.
"""

import numpy as np
from scipy.ndimage import binary_fill_holes, label


def fill_gaps(
    clean_rgb: np.ndarray,
    gap_mask: np.ndarray,
    fill_general_holes: bool = True,
    min_hole_size: int = 4,
) -> np.ndarray:
    """
    Rellena huecos en la imagen limpia de radar.

    Args:
        clean_rgb: Array (H, W, 3) uint8 — imagen ya limpia (sin fondo).
        gap_mask: Array (H, W) bool — True donde hay hueco por marca de agua.
        fill_general_holes: Si True, también rellena huecos internos pequeños.
        min_hole_size: Mínimo de píxeles contiguos para considerar un hueco interno.

    Returns:
        Array (H, W, 3) uint8 con huecos rellenados.
    """
    result = clean_rgb.copy()
    storm_mask = np.any(result > 0, axis=2)  # (H, W) bool

    # FASE 1: Rellenar zona de marca de agua
    if gap_mask.any():
        result = _fill_watermark_region(result, storm_mask, gap_mask)
        # Actualizar storm_mask con los nuevos píxeles rellenados
        storm_mask = np.any(result > 0, axis=2)

    # FASE 2: Huecos internos generales
    if fill_general_holes:
        result = _fill_internal_holes(result, storm_mask, min_hole_size)

    return result


def _fill_watermark_region(
    rgb: np.ndarray,
    storm_mask: np.ndarray,
    gap_mask: np.ndarray,
) -> np.ndarray:
    """
    Fase 1: Rellena la región de marca de agua propagando desde vecinos.

    Estrategia:
    - Iterar los píxeles del hueco en orden de cercanía a píxeles de tormenta.
    - Para cada hueco, buscar vecinos en 4 direcciones que ya sean tormenta.
    - Asignar el color del vecino más representado (más frecuente en los 4 dirs).
    - Sólo rellenar si hay AL MENOS 2 vecinos de tormenta (evita expansión en borde).

    Hacemos múltiples pasadas hasta que no queden huecos rellenables.
    En la práctica converge en 2-4 pasadas para marcas de agua típicas.
    """
    result = rgb.copy()
    current_storm = storm_mask.copy()

    # Píxeles del hueco que necesitan relleno
    gap_coords = list(zip(*np.where(gap_mask & ~current_storm)))

    max_passes = 10  # suficiente para marcas de agua de ~30px de alto
    for _ in range(max_passes):
        filled_any = False
        remaining = []

        for row, col in gap_coords:
            neighbor_colors = _get_storm_neighbors(result, current_storm, row, col)

            # Condición conservadora: al menos 2 vecinos de tormenta
            if len(neighbor_colors) >= 2:
                color = _most_common_color(neighbor_colors)
                result[row, col] = color
                current_storm[row, col] = True
                filled_any = True
            else:
                remaining.append((row, col))

        gap_coords = remaining
        if not filled_any:
            break  # convergió

    return result


def _fill_internal_holes(
    rgb: np.ndarray,
    storm_mask: np.ndarray,
    min_hole_size: int,
) -> np.ndarray:
    """
    Fase 2: Rellena huecos internos completamente rodeados por tormenta.

    Usa binary_fill_holes para encontrar cavidades cerradas, luego
    las rellena con el color mediano de sus vecinos inmediatos.
    Nunca toca píxeles en el borde de la tormenta.
    """
    result = rgb.copy()

    # Encontrar huecos internos: píxeles vacíos completamente rodeados
    filled = binary_fill_holes(storm_mask)
    internal_holes = filled & ~storm_mask  # (H, W) bool

    if not internal_holes.any():
        return result

    # Etiquetar regiones contiguas de huecos
    labeled, num_features = label(internal_holes)

    for region_id in range(1, num_features + 1):
        region = labeled == region_id
        region_size = int(region.sum())

        if region_size < min_hole_size:
            continue  # hueco demasiado pequeño, posiblemente ruido

        # Color de relleno: mediana de los píxeles de tormenta adyacentes a la región
        fill_color = _border_median_color(rgb, storm_mask, region)
        result[region] = fill_color

    return result


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_storm_neighbors(
    rgb: np.ndarray,
    storm_mask: np.ndarray,
    row: int,
    col: int,
) -> list[np.ndarray]:
    """Devuelve los colores de los vecinos en 4 dirs que son tormenta."""
    h, w = storm_mask.shape
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    colors = []
    for dr, dc in directions:
        r, c = row + dr, col + dc
        if 0 <= r < h and 0 <= c < w and storm_mask[r, c]:
            colors.append(rgb[r, c])
    return colors


def _most_common_color(colors: list[np.ndarray]) -> np.ndarray:
    """Devuelve el color más frecuente de la lista (por igualdad exacta de tupla)."""
    # Convertir a tuplas para poder usar como keys de dict
    color_tuples = [tuple(c.tolist()) for c in colors]
    counts: dict[tuple, int] = {}
    for ct in color_tuples:
        counts[ct] = counts.get(ct, 0) + 1
    best = max(counts, key=lambda k: counts[k])
    return np.array(best, dtype=np.uint8)


def _border_median_color(
    rgb: np.ndarray,
    storm_mask: np.ndarray,
    region: np.ndarray,
) -> np.ndarray:
    """
    Calcula la mediana de color de los píxeles de tormenta que bordean la región.
    """
    # Dilatar la región 1px para encontrar su borde externo
    from scipy.ndimage import binary_dilation
    dilated = binary_dilation(region)
    border = dilated & storm_mask & ~region

    if not border.any():
        # Fallback: mediana de toda la tormenta visible
        storm_pixels = rgb[storm_mask]
        return np.median(storm_pixels, axis=0).astype(np.uint8)

    border_pixels = rgb[border]
    return np.median(border_pixels, axis=0).astype(np.uint8)