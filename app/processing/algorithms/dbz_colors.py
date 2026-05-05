"""
Colores DBZ del radar DACC Mendoza.

Cada nivel dBZ tiene un color RGB de referencia. La comparación no puede ser
exacta (==) porque el GIF tiene matices de compresión y anti-aliasing.
Se usa distancia euclidiana en espacio RGB con un umbral configurable.
"""

import numpy as np

# Mapa dBZ → color RGB (hex → tuple)
DBZ_COLOR_MAP: dict[int, tuple[int, int, int]] = {
    10: (0x42, 0x3F, 0x8C),
    20: (0x00, 0x58, 0x05),
    30: (0x00, 0x6F, 0x09),
    35: (0x00, 0x84, 0xDC),
    36: (0x00, 0x52, 0xE9),
    39: (0x6C, 0x27, 0xC7),
    42: (0xD2, 0x1E, 0x85),
    45: (0xC8, 0x66, 0x87),
    48: (0xDB, 0x88, 0x34),
    51: (0xFF, 0xC3, 0x29),
    54: (0xFF, 0xF7, 0x0A),
    57: (0xFF, 0x9B, 0x53),
    60: (0xFF, 0x5F, 0x00),
    65: (0xFF, 0x34, 0x00),
    70: (0xBF, 0xBF, 0xBF),
    80: (0xD4, 0xD4, 0xD4),
}

# Array numpy para vectorizar la búsqueda: shape (N, 3)
_DBZ_VALUES = np.array(list(DBZ_COLOR_MAP.keys()), dtype=np.int32)
_DBZ_COLORS = np.array(list(DBZ_COLOR_MAP.values()), dtype=np.float32)

# Umbral de distancia euclidiana en RGB (0-255 por canal).
# Un valor de 30 es razonable para absorber matices de compresión GIF.
DEFAULT_COLOR_THRESHOLD: float = 30.0


def classify_pixel(r: int, g: int, b: int, threshold: float = DEFAULT_COLOR_THRESHOLD) -> int | None:
    """
    Clasifica un píxel RGB en su nivel dBZ más cercano.

    Devuelve el valor dBZ si la distancia al color más cercano
    está dentro del umbral, o None si no corresponde a ningún nivel.
    """
    pixel = np.array([r, g, b], dtype=np.float32)
    distances = np.linalg.norm(_DBZ_COLORS - pixel, axis=1)
    min_idx = int(np.argmin(distances))
    if distances[min_idx] <= threshold:
        return int(_DBZ_VALUES[min_idx])
    return None


def classify_array(rgb_array: np.ndarray, threshold: float = DEFAULT_COLOR_THRESHOLD) -> np.ndarray:
    """
    Clasifica un array RGB completo (H, W, 3) en niveles dBZ.

    Devuelve array (H, W) con el dBZ correspondiente o 0 donde no hay tormenta.
    Vectorizado sobre todos los píxeles a la vez — eficiente para arrays grandes.
    """
    h, w, _ = rgb_array.shape
    flat = rgb_array.reshape(-1, 3).astype(np.float32)  # (N, 3)

    # Distancias: (N, num_dbz_levels)
    diff = flat[:, np.newaxis, :] - _DBZ_COLORS[np.newaxis, :, :]  # (N, K, 3)
    distances = np.linalg.norm(diff, axis=2)  # (N, K)

    min_idx = np.argmin(distances, axis=1)       # (N,)
    min_dist = distances[np.arange(len(flat)), min_idx]  # (N,)

    result = np.zeros(len(flat), dtype=np.int32)
    mask = min_dist <= threshold
    result[mask] = _DBZ_VALUES[min_idx[mask]]

    return result.reshape(h, w)