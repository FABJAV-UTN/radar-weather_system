"""Router para endpoints de consulta de imágenes de radar."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from shapely import wkt

from app.core.config import settings
from app.data.database import get_db
from app.data.models.radar_image import RadarImage
from app.presentation.schemas.images import (
    RadarImageResponse,
    RadarImageListResponse,
    RadarImageStatsResponse,
    RadarImageMetadataResponse,
    DeleteImageResponse,
    SourceTypeCount,
    MonthlyCount,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/images", tags=["images"])


def _extent_to_geojson(extent_wkt: Optional[str]) -> Optional[dict]:
    """Convierte WKT de PostGIS a GeoJSON FeatureCollection."""
    if not extent_wkt:
        return None
    
    try:
        geometry = wkt.loads(extent_wkt)
        # Convertir a GeoJSON
        from shapely.geometry import mapping
        geojson = mapping(geometry)
        return geojson
    except Exception as e:
        logger.warning("Error convirtiendo extent a GeoJSON: %s", e)
        return None


def _build_download_url(request: Request, file_path: str) -> str:
    """Construye la URL completa para descargar un GeoTIFF."""
    # URL: {base_url}data/geotiffs/{file_path}
    return f"{request.base_url}data/geotiffs/{file_path}"


def _radar_image_to_response(
    image: RadarImage, request: Request
) -> RadarImageResponse:
    """Convierte un objeto RadarImage a RadarImageResponse."""
    return RadarImageResponse(
        id=image.id,
        location=image.location,
        filename=image.filename,
        file_path=image.file_path,
        image_timestamp=image.image_timestamp,
        source_type=image.source_type,
        datotif_id=image.datotif_id,
        created_at=image.created_at,
        download_url=_build_download_url(request, image.file_path),
        extent_geojson=_extent_to_geojson(image.extent),
        metadata=RadarImageMetadataResponse(
            width_px=image.width_px,
            height_px=image.height_px,
            max_dbz=image.max_dbz,
            storm_pixel_count=image.storm_pixel_count,
            extent_geojson=_extent_to_geojson(image.extent),
        ),
    )


@router.get("/stats", response_model=RadarImageStatsResponse)
async def get_stats(
    session: AsyncSession = Depends(get_db),
) -> RadarImageStatsResponse:
    """
    Retorna estadísticas agregadas de las imágenes.
    
    Incluye:
    - Total de imágenes
    - Conteo por tipo de fuente
    - dBZ máximo global
    - Rango de fechas (min, max)
    - Conteo por mes (últimos 12 meses)
    """
    logger.info("Calculando estadísticas")

    try:
        # Total
        total_result = await session.execute(select(func.count(RadarImage.id)))
        total_images = total_result.scalar() or 0

        # Por source_type
        source_counts_result = await session.execute(
            select(
                RadarImage.source_type,
                func.count(RadarImage.id).label("count")
            ).group_by(RadarImage.source_type)
        )
        by_source_type = [
            SourceTypeCount(source_type=row[0], count=row[1])
            for row in source_counts_result
        ]

        # Max dBZ global
        max_dbz_result = await session.execute(
            select(func.max(RadarImage.max_dbz))
        )
        max_dbz_global = max_dbz_result.scalar()

        # Rango de fechas
        date_range_result = await session.execute(
            select(
                func.min(RadarImage.image_timestamp),
                func.max(RadarImage.image_timestamp)
            )
        )
        date_min, date_max = date_range_result.first() or (None, None)

        # Conteo por mes (últimos 12 meses)
        now = datetime.now()
        twelve_months_ago = now - timedelta(days=365)
        
        monthly_counts_result = await session.execute(
            select(
                func.extract("year", RadarImage.image_timestamp).label("year"),
                func.extract("month", RadarImage.image_timestamp).label("month"),
                func.count(RadarImage.id).label("count")
            )
            .where(RadarImage.image_timestamp >= twelve_months_ago)
            .group_by(
                func.extract("year", RadarImage.image_timestamp),
                func.extract("month", RadarImage.image_timestamp)
            )
            .order_by(
                func.extract("year", RadarImage.image_timestamp),
                func.extract("month", RadarImage.image_timestamp)
            )
        )
        
        by_month = [
            MonthlyCount(year=int(row[0]), month=int(row[1]), count=row[2])
            for row in monthly_counts_result
        ]

        logger.info(
            "Estadísticas: total=%d, sources=%d, max_dbz=%s, meses=%d",
            total_images,
            len(by_source_type),
            max_dbz_global,
            len(by_month)
        )

        return RadarImageStatsResponse(
            total_images=total_images,
            by_source_type=by_source_type,
            max_dbz_global=max_dbz_global,
            date_range_min=date_min,
            date_range_max=date_max,
            by_month=by_month,
        )

    except Exception as e:
        logger.error("Error calculando estadísticas: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=RadarImageListResponse)
async def list_images(
    location: Optional[str] = Query(None, description="Filtrar por ubicación"),
    date_from: Optional[str] = Query(None, description="Fecha mínima (ISO 8601)"),
    date_to: Optional[str] = Query(None, description="Fecha máxima (ISO 8601)"),
    limit: int = Query(100, ge=1, le=1000, description="Límite de items"),
    offset: int = Query(0, ge=0, description="Offset desde el inicio"),
    request: Request = None,
    session: AsyncSession = Depends(get_db),
) -> RadarImageListResponse:
    """
    Lista todas las imágenes con filtros opcionales.
    
    Parámetros:
    - location: Filtrar por ubicación (ej: "san_rafael")
    - date_from: Fecha mínima en formato ISO 8601 (ej: "2026-01-01")
    - date_to: Fecha máxima en formato ISO 8601 (ej: "2026-12-31")
    - limit: Cantidad máxima de resultados (default 100, máx 1000)
    - offset: Saltar N resultados (para paginación)
    """
    logger.info(
        "Listando imágenes: location=%s, date_from=%s, date_to=%s, limit=%d, offset=%d",
        location, date_from, date_to, limit, offset
    )

    try:
        # Parsear fechas
        dt_from = None
        dt_to = None
        
        if date_from:
            dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        if date_to:
            dt_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))

        # Construir query
        stmt = select(RadarImage)
        
        # Filtros
        filters = []
        if location:
            filters.append(RadarImage.location == location)
        if dt_from:
            filters.append(RadarImage.image_timestamp >= dt_from)
        if dt_to:
            filters.append(RadarImage.image_timestamp <= dt_to)
        
        if filters:
            stmt = stmt.where(and_(*filters))

        # Contar total
        count_stmt = select(func.count(RadarImage.id))
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        
        count_result = await session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Ordenar y paginar
        stmt = (
            stmt.order_by(RadarImage.image_timestamp.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await session.execute(stmt)
        images = list(result.scalars().all())

        logger.info("Encontradas %d imágenes (total: %d)", len(images), total)

        return RadarImageListResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=[_radar_image_to_response(img, request) for img in images],
        )

    except ValueError as e:
        logger.error("Error parseando parámetros: %s", e)
        raise HTTPException(status_code=400, detail=f"Error parseando parámetros: {str(e)}")
    except Exception as e:
        logger.error("Error listando imágenes: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{image_id}", response_model=RadarImageResponse)
async def get_image(
    image_id: int,
    request: Request = None,
    session: AsyncSession = Depends(get_db),
) -> RadarImageResponse:
    """
    Obtiene una imagen específica por ID.
    
    Retorna todos los campos incluyendo URL de descarga y extent como GeoJSON.
    """
    logger.info("Obteniendo imagen ID=%d", image_id)

    try:
        result = await session.execute(
            select(RadarImage).where(RadarImage.id == image_id)
        )
        image = result.scalar_one_or_none()

        if not image:
            logger.warning("Imagen no encontrada: ID=%d", image_id)
            raise HTTPException(status_code=404, detail=f"Imagen con ID {image_id} no encontrada")

        return _radar_image_to_response(image, request)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error obteniendo imagen: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{image_id}/metadata", response_model=RadarImageMetadataResponse)
async def get_image_metadata(
    image_id: int,
    session: AsyncSession = Depends(get_db),
) -> RadarImageMetadataResponse:
    """
    Obtiene solo los metadatos de una imagen.
    
    Retorna: dimensiones, max_dbz, storm_pixel_count, extent GeoJSON.
    """
    logger.info("Obteniendo metadatos de imagen ID=%d", image_id)

    try:
        result = await session.execute(
            select(RadarImage).where(RadarImage.id == image_id)
        )
        image = result.scalar_one_or_none()

        if not image:
            logger.warning("Imagen no encontrada: ID=%d", image_id)
            raise HTTPException(status_code=404, detail=f"Imagen con ID {image_id} no encontrada")

        return RadarImageMetadataResponse(
            width_px=image.width_px,
            height_px=image.height_px,
            max_dbz=image.max_dbz,
            storm_pixel_count=image.storm_pixel_count,
            extent_geojson=_extent_to_geojson(image.extent),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error obteniendo metadatos: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{image_id}", response_model=DeleteImageResponse)
async def delete_image(
    image_id: int,
    session: AsyncSession = Depends(get_db),
) -> DeleteImageResponse:
    """
    Elimina una imagen de la DB y del disco.
    
    Elimina:
    1. El registro de la base de datos
    2. El archivo GeoTIFF del disco
    """
    logger.info("Eliminando imagen ID=%d", image_id)

    try:
        # Obtener la imagen
        result = await session.execute(
            select(RadarImage).where(RadarImage.id == image_id)
        )
        image = result.scalar_one_or_none()

        if not image:
            logger.warning("Imagen no encontrada para eliminar: ID=%d", image_id)
            raise HTTPException(status_code=404, detail=f"Imagen con ID {image_id} no encontrada")

        # Construir path absoluto
        storage_root = Path(settings.geotiff_storage_path)
        absolute_path = storage_root / image.file_path

        # Eliminar archivo del disco
        deleted_from_disk = False
        if absolute_path.exists():
            try:
                absolute_path.unlink()
                deleted_from_disk = True
                logger.info("Archivo eliminado del disco: %s", absolute_path)
            except Exception as e:
                logger.error("Error eliminando archivo del disco: %s", e)
                # Continuamos igual, eliminaremos de la DB
        else:
            logger.warning("Archivo no encontrado en disco: %s", absolute_path)

        # Eliminar de la DB
        await session.delete(image)
        await session.commit()
        logger.info("Imagen eliminada de la DB: ID=%d", image_id)

        message = "Imagen eliminada"
        if deleted_from_disk:
            message += " (archivo eliminado del disco)"
        else:
            message += " (archivo no encontrado en disco)"

        return DeleteImageResponse(
            success=True,
            id=image_id,
            message=message,
        )

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error("Error eliminando imagen: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
