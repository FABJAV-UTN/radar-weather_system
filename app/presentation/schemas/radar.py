"""Esquemas Pydantic para endpoints de radar."""

from datetime import datetime
from pydantic import BaseModel, Field


class ProcessedImageInfo(BaseModel):
    """Información de una imagen procesada."""
    filename: str = Field(..., description="Nombre del GeoTIFF generado")
    file_path: str = Field(..., description="Path relativo al storage")
    timestamp: datetime = Field(..., description="Timestamp de la imagen (UTC-3)")
    source_type: str = Field(..., description="Fuente: dacc_api, local_bank, cloud_bank")


class ProcessLocalResponse(BaseModel):
    """Respuesta del endpoint process-local."""
    total_images: int = Field(..., description="Cantidad total de GIFs encontrados")
    processed: int = Field(..., description="Cantidad procesadas exitosamente")
    failed: int = Field(..., description="Cantidad que fallaron")
    generated_files: list[ProcessedImageInfo] = Field(
        default_factory=list,
        description="Detalle de archivos generados"
    )
    errors: dict[str, str] = Field(
        default_factory=dict,
        description="Mapeo filename → error message"
    )


class ProcessDACCResponse(BaseModel):
    """Respuesta del endpoint process-dacc."""
    success: bool = Field(..., description="Si el procesamiento fue exitoso")
    filename: str | None = Field(default=None, description="Nombre del GeoTIFF generado")
    file_path: str | None = Field(default=None, description="Path relativo al storage")
    timestamp: datetime | None = Field(
        default=None,
        description="Timestamp detectado en la imagen (UTC-3)"
    )
    datotif_id: int | None = Field(default=None, description="ID del datotif usado (1, 2, 3)")
    error: str | None = Field(default=None, description="Mensaje de error si falló")


class ProcessDACCControlResponse(BaseModel):
    """Respuesta de control del loop DACC."""
    status: str = Field(..., description="Estado del loop: started o stopped")


class DACCStatusResponse(BaseModel):
    """Estado del loop DACC."""
    is_running: bool = Field(..., description="Si el loop DACC está activo")
    started_at: datetime | None = Field(
        default=None,
        description="Fecha y hora en que se inició el loop (UTC-3)",
    )
    last_download_at: datetime | None = Field(
        default=None,
        description="Fecha y hora de la última descarga DACC (UTC-3)",
    )
    last_image_timestamp: datetime | None = Field(
        default=None,
        description="Timestamp extraído de la última imagen válida (UTC-3)",
    )
    total_processed_this_session: int = Field(
        default=0,
        description="Cantidad de imágenes procesadas en esta sesión",
    )
    total_skipped_duplicates: int = Field(
        default=0,
        description="Cantidad de imágenes duplicadas saltadas",
    )
    total_discarded_invalid: int = Field(
        default=0,
        description="Cantidad de imágenes inválidas descartadas",
    )
    next_run_in_seconds: int = Field(
        default=0,
        description="Segundos restantes hasta la próxima ejecución del loop",
    )


class SystemStatusResponse(BaseModel):
    """Respuesta del endpoint status."""
    database_images_count: int = Field(..., description="Cantidad de imágenes en DB")
    configured_source: str = Field(..., description="Fuente configurada: local, dacc_api, cloud_bank")
    geotiff_storage_path: str = Field(..., description="Path donde se almacenan los GeoTIFFs")
    disk_free_gb: float = Field(..., description="Espacio libre en disco (GB)")
    disk_available_for_storage: bool = Field(
        ...,
        description="True si hay al menos 1 GB disponible"
    )
