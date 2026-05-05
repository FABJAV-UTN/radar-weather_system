"""Router para endpoints de procesamiento de radar."""

import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.core.config import settings
from app.data.database import get_db
from app.data.models.radar_image import RadarImage
from app.presentation.schemas.radar import (
    ProcessLocalResponse,
    ProcessDACCResponse,
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
                output_path = await pipeline.process(
                    image_path=image_path,
                    source_type="local_bank",
                    fallback_timestamp=datetime.now(),
                )

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


@router.post("/process-dacc", response_model=ProcessDACCResponse)
async def process_dacc(
    session: AsyncSession = Depends(get_db),
    geo_loader: GeoReferenceLoader = Depends(get_geo_loader),
) -> ProcessDACCResponse:
    """
    Descarga latest.gif de la API DACC y lo procesa.

    Guarda temporalmente en /tmp/, procesa con source_type="dacc_api"
    y retorna el path del GeoTIFF generado.
    """
    logger.info("Iniciando procesamiento de DACC API")
    response = ProcessDACCResponse(success=False)

    try:
        # Obtener la fuente DACC
        source = get_image_source()
        
        if source.__class__.__name__ != "DACCApiSource":
            # Intentar crear DACCApiSource explícitamente
            from app.processing.services.dacc_api_source import DACCApiSource
            source = DACCApiSource()

        # Crear archivo temporal
        temp_dir = Path(tempfile.gettempdir())
        temp_file = temp_dir / "dacc_latest.gif"
        
        logger.info("Descargando latest.gif de DACC API a %s", temp_file)
        
        # Descargar la imagen
        try:
            temp_file = await source.fetch("latest.gif", destination=temp_file)
        except Exception as e:
            response.error = f"Error descargando desde DACC API: {str(e)}"
            logger.error("Error descargando: %s", response.error)
            return response

        # Procesar la imagen
        try:
            pipeline = RadarPipeline(geo_loader, session)
            
            # Usar fecha actual como fallback si el OCR no puede extraer timestamp
            output_path = await pipeline.process(
                image_path=temp_file,
                source_type="dacc_api",
                fallback_timestamp=datetime.now(),
            )

            if output_path is not None:
                # Obtener timestamp y datotif_id de la DB
                result = await session.execute(
                    select(RadarImage).where(
                        RadarImage.filename == output_path.name
                    )
                )
                db_record = result.scalar_one_or_none()
                
                response.success = True
                response.filename = output_path.name
                response.file_path = str(output_path.relative_to(settings.geotiff_storage_path))
                response.timestamp = db_record.image_timestamp if db_record else datetime.now()
                response.datotif_id = db_record.datotif_id if db_record else 1
                
                logger.info("✓ DACC procesado exitosamente: %s", output_path.name)
            else:
                response.error = "Pipeline retornó None (imagen descartada)"
                logger.warning("Pipeline retornó None")

        except Exception as e:
            response.error = f"Error en pipeline: {str(e)}"
            logger.error("Error en pipeline: %s", e, exc_info=True)

        finally:
            # Limpiar archivo temporal
            if temp_file.exists():
                try:
                    temp_file.unlink()
                    logger.info("Archivo temporal eliminado: %s", temp_file)
                except Exception as e:
                    logger.warning("No se pudo eliminar archivo temporal: %s", e)

        await session.commit()

    except Exception as e:
        response.error = f"Error crítico: {str(e)}"
        logger.error("Error crítico en process_dacc: %s", e, exc_info=True)

    return response


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
