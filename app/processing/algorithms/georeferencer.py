"""
Geolocalización de imágenes de radar → GeoTIFF.

Los datotifs son archivos GeoTIFF de referencia que contienen la
transformación geográfica (CRS, transform) correspondiente a cada
tipo de imagen de radar.

Tipos:
    datotif1: Imágenes del DACC API (latest.gif)
    datotif2: Banco local, imágenes con ancho <= 799px
    datotif3: Banco local, imágenes con ancho > 799px

Los datotifs se cargan UNA SOLA VEZ al inicio del proceso y se
reutilizan para todas las imágenes. Son archivos de sólo lectura.

IMPORTANTE: Los datotifs no están disponibles todavía. El código
está preparado para recibirlos. Para tests, se usa un transform
placeholder que no es geográficamente correcto pero permite validar
el pipeline completo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine

logger = logging.getLogger(__name__)

# Directorio donde se colocarán los datotifs cuando estén disponibles.
# Cambiar esta constante cuando tengas los archivos reales.
DATOTIF_DIR: Path = Path("data/geo_templates")

DATOTIF_FILENAMES: dict[int, str] = {
    1: "datos_geo.tif",   # DACC API / cloud bank
    2: "tif700.tif",      # banco local, lado < 799px
    3: "tif800.tif",      # banco local, lado >= 799px
}


@dataclass(frozen=True)
class GeoReference:
    """Referencia geográfica extraída de un datotif."""
    crs: CRS
    transform: Affine
    width: int
    height: int
    datotif_id: int


class GeoReferenceLoader:
    """
    Carga y cachea los datotifs en memoria.

    Diseñado para instanciarse UNA VEZ y pasarse a todas las imágenes.
    Uso típico:

        loader = GeoReferenceLoader()
        loader.load_all()

        # Luego, para cada imagen:
        geo = loader.get(datotif_id=1)
        geotiff = apply_geo_reference(pixel_array, geo)
    """

    def __init__(self, datotif_dir: Path | None = None):
        self._dir = datotif_dir or DATOTIF_DIR
        self._cache: dict[int, GeoReference] = {}

    def load_all(self) -> None:
        """Carga los 3 datotifs en memoria. Llamar al inicio del proceso."""
        for datotif_id, filename in DATOTIF_FILENAMES.items():
            path = self._dir / filename
            if not path.exists():
                logger.warning(
                    "Datotif %d no encontrado en %s — usando placeholder para tests.",
                    datotif_id, path
                )
                self._cache[datotif_id] = _placeholder_geo_reference(datotif_id)
                continue

            with rasterio.open(path) as src:
                self._cache[datotif_id] = GeoReference(
                    crs=src.crs,
                    transform=src.transform,
                    width=src.width,
                    height=src.height,
                    datotif_id=datotif_id,
                )
            logger.info("Datotif %d cargado desde %s", datotif_id, path)

    def get(self, datotif_id: int) -> GeoReference:
        """Devuelve la referencia geográfica para el datotif indicado."""
        if datotif_id not in self._cache:
            raise KeyError(
                f"Datotif {datotif_id} no cargado. Llamá load_all() primero."
            )
        return self._cache[datotif_id]

    def is_placeholder(self, datotif_id: int) -> bool:
        """True si el datotif es un placeholder (no hay archivo real aún)."""
        return self._cache.get(datotif_id) is not None and \
               self._cache[datotif_id].crs.to_epsg() == 4326  # placeholder usa WGS84


def apply_geo_reference(
    pixel_array: np.ndarray,
    geo: GeoReference,
    output_path: Path,
) -> Path:
    """
    Escribe el array de píxeles como GeoTIFF georreferenciado.

    Args:
        pixel_array: Array (H, W, 3) uint8 con la imagen limpia.
        geo: Referencia geográfica del datotif correspondiente.
        output_path: Ruta donde guardar el GeoTIFF resultado.

    Returns:
        output_path (para encadenamiento).
    """
    h, w = pixel_array.shape[:2]

    with rasterio.open(
        output_path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=3,           # R, G, B
        dtype=rasterio.uint8,
        crs=geo.crs,
        transform=geo.transform,
        compress="lzw",    # compresión sin pérdida, estándar para raster
    ) as dst:
        # rasterio espera (bands, H, W)
        dst.write(pixel_array[:, :, 0], 1)  # R
        dst.write(pixel_array[:, :, 1], 2)  # G
        dst.write(pixel_array[:, :, 2], 3)  # B

    return output_path


# ─── Placeholder para tests ───────────────────────────────────────────────────

def _placeholder_geo_reference(datotif_id: int) -> GeoReference:
    """
    Placeholder geográfico para usar cuando el datotif real no está disponible.

    Usa coordenadas aproximadas centradas en San Rafael, Mendoza.
    NO usar en producción — sólo para tests del pipeline.
    """
    from app.core.constanst import AREA_FOCAL_BOUNDS, EPSG_CODE

    b = AREA_FOCAL_BOUNDS
    pixel_size = 0.009  # grados por píxel (aprox 900m en esta latitud)

    transform = Affine(
        pixel_size, 0.0, b["lon_min"],
        0.0, -pixel_size, b["lat_max"],
    )

    try:
        crs = CRS.from_epsg(EPSG_CODE)
    except Exception:
        crs = CRS.from_epsg(4326)  # WGS84 como fallback absoluto

    return GeoReference(
        crs=crs,
        transform=transform,
        width=300,
        height=300,
        datotif_id=datotif_id,
    )