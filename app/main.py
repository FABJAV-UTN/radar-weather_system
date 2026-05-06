"""Entry point FastAPI."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.scheduler import DACCScheduler
from app.presentation.api.v1 import radar_router, images_router
from app.processing.algorithms.georeferencer import GeoReferenceLoader

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan de la aplicación.
    
    - startup: Instancia el GeoReferenceLoader y lo almacena en app.state
    - shutdown: Limpia recursos si es necesario
    """
    logger.info("Iniciando aplicación Radar Weather System")
    
    # Startup: cargar GeoReferences
    try:
        geo_loader = GeoReferenceLoader()
        geo_loader.load_all()
        app.state.geo_loader = geo_loader
        app.state.dacc_scheduler = DACCScheduler(geo_loader=geo_loader)
        logger.info("✓ GeoReferenceLoader inicializado y cacheado en app.state")
        logger.info("✓ DACCScheduler inicializado y disponible en app.state")
    except Exception as e:
        logger.error("✗ Error inicializando GeoReferenceLoader: %s", e, exc_info=True)
        raise
    
    yield
    
    # Shutdown: limpieza (si es necesaria)
    if getattr(app.state, "dacc_scheduler", None) is not None:
        scheduler = app.state.dacc_scheduler
        if scheduler.is_running():
            logger.info("Deteniendo DACCScheduler en shutdown")
            try:
                await scheduler.stop()
            except Exception as e:
                logger.warning("Error deteniendo DACCScheduler en shutdown: %s", e)
    logger.info("Cerrando aplicación Radar Weather System")


app = FastAPI(
    title="Radar Weather System",
    description="Análisis de radares meteorológicos - San Rafael, Mendoza",
    version="0.1.0",
    lifespan=lifespan,
)

# Registrar routers
app.include_router(radar_router)
app.include_router(images_router)

# Montar archivos estáticos para servir GeoTIFFs
# URL: /data/geotiffs/{file_path}
geotiff_storage = Path(settings.geotiff_storage_path)
geotiff_storage.mkdir(parents=True, exist_ok=True)
app.mount(
    "/data/geotiffs",
    StaticFiles(directory=str(geotiff_storage)),
    name="geotiffs"
)
logger.info("Sirviendo GeoTIFFs desde: %s", geotiff_storage)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "radar-weather-system"}
