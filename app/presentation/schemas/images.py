"""Esquemas Pydantic para endpoints de imágenes de radar."""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class RadarImageMetadataResponse(BaseModel):
    """Metadatos de una imagen de radar."""
    width_px: Optional[int] = Field(None, description="Ancho en píxeles")
    height_px: Optional[int] = Field(None, description="Alto en píxeles")
    max_dbz: Optional[float] = Field(None, description="dBZ máximo detectado")
    storm_pixel_count: Optional[int] = Field(None, description="Cantidad de píxeles con tormenta")
    extent_geojson: Optional[dict[str, Any]] = Field(
        None,
        description="Bounding box como polígono GeoJSON (EPSG:4326)"
    )


class RadarImageResponse(BaseModel):
    """Respuesta completa de una imagen de radar."""
    id: int = Field(..., description="ID único")
    location: str = Field(..., description="Ubicación (ej: san_rafael)")
    filename: str = Field(..., description="Nombre del archivo GeoTIFF")
    file_path: str = Field(..., description="Path relativo al storage")
    image_timestamp: datetime = Field(..., description="Timestamp de la imagen (UTC-3)")
    source_type: str = Field(..., description="Fuente: dacc_api, local_bank, cloud_bank")
    datotif_id: int = Field(..., description="ID del datotif usado (1, 2, 3)")
    created_at: datetime = Field(..., description="Timestamp de creación del registro en DB")
    download_url: str = Field(..., description="URL para descargar el GeoTIFF")
    extent_geojson: Optional[dict[str, Any]] = Field(
        None,
        description="Bounding box como polígono GeoJSON (EPSG:4326)"
    )
    metadata: RadarImageMetadataResponse = Field(..., description="Metadatos de la imagen")

    class Config:
        from_attributes = True


class RadarImageListResponse(BaseModel):
    """Respuesta paginada de imágenes."""
    total: int = Field(..., description="Total de imágenes que coinciden con los filtros")
    limit: int = Field(..., description="Límite de items por página")
    offset: int = Field(..., description="Offset desde el inicio")
    items: list[RadarImageResponse] = Field(..., description="Imágenes de esta página")

    class Config:
        from_attributes = True


class MonthlyCount(BaseModel):
    """Conteo de imágenes por mes."""
    year: int = Field(..., description="Año")
    month: int = Field(..., description="Mes (1-12)")
    count: int = Field(..., description="Cantidad de imágenes")


class SourceTypeCount(BaseModel):
    """Conteo de imágenes por fuente."""
    source_type: str = Field(..., description="Tipo de fuente")
    count: int = Field(..., description="Cantidad de imágenes")


class RadarImageStatsResponse(BaseModel):
    """Estadísticas agregadas de imágenes."""
    total_images: int = Field(..., description="Total de imágenes en la DB")
    by_source_type: list[SourceTypeCount] = Field(..., description="Conteo por tipo de fuente")
    max_dbz_global: Optional[float] = Field(..., description="dBZ máximo global")
    date_range_min: Optional[datetime] = Field(None, description="Timestamp más antiguo")
    date_range_max: Optional[datetime] = Field(None, description="Timestamp más reciente")
    by_month: list[MonthlyCount] = Field(
        default_factory=list,
        description="Conteo por mes (últimos 12 meses)"
    )


class DeleteImageResponse(BaseModel):
    """Respuesta de eliminación de imagen."""
    success: bool = Field(..., description="Si la eliminación fue exitosa")
    id: int = Field(..., description="ID de la imagen eliminada")
    message: str = Field(..., description="Mensaje descriptivo")
