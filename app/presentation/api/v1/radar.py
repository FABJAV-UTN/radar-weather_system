"""Router para endpoints de procesamiento de radar."""

import logging
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.core.config import settings
from app.core.scheduler import DACCScheduler
from app.data.database import get_db
from app.data.models.radar_image import RadarImage
from app.presentation.schemas.radar import (
    ProcessLocalResponse,
    ProcessDACCControlResponse,
    DACCStatusResponse,
    SystemStatusResponse,
    ProcessedImageInfo,
)
from app.processing.algorithms.georeferencer import GeoReferenceLoader
from app.processing.services.factory import get_image_source
from app.processing.services.radar_pipeline import RadarPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/radar", tags=["radar"])


async def get_geo_loader(request: Request) -> GeoReferenceLoader:
    """Obtiene el GeoReferenceLoader del estado de la app."""
    return request.app.state.geo_loader


async def count_images_in_db(session: AsyncSession) -> int:
    """Cuenta la cantidad de imágenes procesadas en la DB."""
    stmt = select(func.count(RadarImage.id))
    result = await session.execute(stmt)
    return result.scalar() or 0


@router.post("/process-local", response_model=ProcessLocalResponse)
async def process_local(
    session: AsyncSession = Depends(get_db),
    geo_loader: GeoReferenceLoader = Depends(get_geo_loader),
) -> ProcessLocalResponse:
    """
    Procesa TODAS las imágenes GIF del banco local.

    Lee archivos desde IMAGE_SOURCE_PATH (configurado en .env),
    procesa cada uno y guarda los GeoTIFFs generados.
    """
    logger.info("Iniciando procesamiento de banco local")
    response = ProcessLocalResponse(
        total_images=0,
        processed=0,
        failed=0,
        generated_files=[],
        errors={},
    )

    try:
        # Obtener la fuente de imágenes (debe estar configurada como "local")
        if settings.image_source_type != "local":
            raise ValueError(
                f"Fuente configurada no es 'local': {settings.image_source_type}. "
                f"Configura IMAGE_SOURCE_TYPE=local en .env"
            )

        source = get_image_source()
        
        # Listar todos los GIFs disponibles
        # Usar fechas amplias para capturar todas las imágenes
        entries = await source.list_available(
            date_from="2000-01-01",
            date_to="2099-12-31",
        )
        response.total_images = len(entries)
        logger.info("Encontrados %d GIFs en el banco local", response.total_images)

        # Procesar cada imagen
        pipeline = RadarPipeline(geo_loader, session)
        for entry in entries:
            try:
                logger.info("Procesando: %s", entry.filename)
                
                # Obtener path de la imagen
                image_path: Path = entry.file_path
                if isinstance(image_path, str):
                    image_path = Path(image_path)

                # Procesar imagen
                output_path = await pipeline.process_local(image_path=image_path)

                if output_path is not None:
                    response.processed += 1
                    response.generated_files.append(
                        ProcessedImageInfo(
                            filename=output_path.name,
                            file_path=str(output_path.relative_to(settings.geotiff_storage_path)),
                            timestamp=entry.timestamp or datetime.now(),
                            source_type="local_bank",
                        )
                    )
                    logger.info("✓ Generado: %s", output_path.name)
                else:
                    response.failed += 1
                    response.errors[entry.filename] = "Pipeline retornó None"
                    logger.warning("✗ Falló procesamiento de %s", entry.filename)

            except Exception as e:
                response.failed += 1
                response.errors[entry.filename] = str(e)
                logger.error("✗ Error procesando %s: %s", entry.filename, e, exc_info=True)

        await session.commit()
        logger.info(
            "Procesamiento completado: %d ok, %d failed de %d",
            response.processed,
            response.failed,
            response.total_images,
        )

    except Exception as e:
        logger.error("Error crítico en process_local: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    return response


@router.post("/process-dacc", response_model=ProcessDACCControlResponse)
async def process_dacc(
    request: Request,
) -> ProcessDACCControlResponse:
    """
    Inicia el loop de descarga y procesamiento DACC en background.
    """
    scheduler: DACCScheduler | None = getattr(request.app.state, "dacc_scheduler", None)
    if scheduler is None:
        logger.error("DACC scheduler no inicializado en app.state")
        raise HTTPException(status_code=500, detail="DACC scheduler no inicializado")

    if scheduler.is_running():
        raise HTTPException(status_code=409, detail="Loop DACC ya está activo")

    try:
        await scheduler.start()
    except RuntimeError as exc:
        logger.error("Error iniciando loop DACC: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    logger.info("Loop DACC iniciado")
    return ProcessDACCControlResponse(status="started")


@router.post("/process-dacc/stop", response_model=ProcessDACCControlResponse)
async def stop_dacc(
    request: Request,
) -> ProcessDACCControlResponse:
    """Detiene el loop DACC de forma graceful."""
    scheduler: DACCScheduler | None = getattr(request.app.state, "dacc_scheduler", None)
    if scheduler is None:
        logger.error("DACC scheduler no inicializado en app.state")
        raise HTTPException(status_code=500, detail="DACC scheduler no inicializado")

    if not scheduler.is_running():
        raise HTTPException(status_code=404, detail="Loop DACC no está activo")

    await scheduler.stop()
    logger.info("Loop DACC detenido")
    return ProcessDACCControlResponse(status="stopped")


@router.get("/process-dacc/status", response_model=DACCStatusResponse)
async def status_dacc(
    request: Request,
) -> DACCStatusResponse:
    """Retorna el estado del loop DACC."""
    scheduler: DACCScheduler | None = getattr(request.app.state, "dacc_scheduler", None)
    if scheduler is None:
        logger.error("DACC scheduler no inicializado en app.state")
        raise HTTPException(status_code=500, detail="DACC scheduler no inicializado")

    return scheduler.get_status()


@router.get("/status", response_model=SystemStatusResponse)
async def get_status(
    session: AsyncSession = Depends(get_db),
) -> SystemStatusResponse:
    """
    Retorna el estado del sistema.

    Incluye: cantidad de imágenes en DB, fuente configurada,
    path de storage y espacio en disco disponible.
    """
    logger.info("Consultando estado del sistema")

    try:
        # Contar imágenes en DB
        images_count = await count_images_in_db(session)
        
        # Obtener path de storage
        storage_path = Path(settings.geotiff_storage_path)
        
        # Calcular espacio en disco disponible
        disk_stat = shutil.disk_usage(str(storage_path) if storage_path.exists() else "/")
        disk_free_gb = disk_stat.free / (1024 ** 3)  # Convertir a GB
        
        response = SystemStatusResponse(
            database_images_count=images_count,
            configured_source=settings.image_source_type,
            geotiff_storage_path=str(storage_path),
            disk_free_gb=round(disk_free_gb, 2),
            disk_available_for_storage=disk_free_gb >= 1.0,
        )
        
        logger.info(
            "Estado: %d imágenes en DB, fuente=%s, espacio libre=%.2f GB",
            images_count,
            settings.image_source_type,
            disk_free_gb,
        )
        
        return response

    except Exception as e:
        logger.error("Error al consultar estado: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
