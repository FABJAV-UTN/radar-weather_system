"""
Tests de integración del DACCScheduler.

Usan componentes reales (GeoReferenceLoader con placeholders, imágenes PIL sintéticas)
para validar el flujo completo sin mocks excesivos.
"""

import asyncio
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

_real_wait_for = asyncio.wait_for

from app.core.scheduler import DACCScheduler
from app.processing.algorithms.georeferencer import GeoReferenceLoader


class TestDACCSchedulerIntegration:
    """Tests de integración del scheduler con componentes reales."""

    @pytest.fixture
    def geo_loader(self, tmp_path: Path):
        """GeoReferenceLoader con placeholders."""
        loader = GeoReferenceLoader(datotif_dir=tmp_path)
        loader.load_all()  # Usa placeholders
        return loader

    @pytest.fixture
    def synthetic_image_with_timestamp(self):
        """Imagen PIL sintética con timestamp simulable."""
        # Crear imagen con texto que simule timestamp
        img = Image.new("RGB", (400, 300), color=(255, 255, 255))
        # En tests reales, podríamos dibujar texto, pero para mockeamos extract_timestamp
        return img

    @pytest.mark.asyncio
    async def test_scheduler_multiple_ticks_with_mocked_sleep(self, geo_loader, tmp_path):
        """Scheduler corre 3 ticks, se autodetiene, verifica contadores."""
        scheduler = DACCScheduler(geo_loader)

        # Mock para controlar el loop: hacer 3 ticks y detener
        tick_count = 0

        async def mock_wait(awaitable, timeout):
            nonlocal tick_count
            tick_count += 1
            if tick_count >= 3:
                scheduler._stop_event.set()
            try:
                return await _real_wait_for(awaitable, timeout=0.01)
            except asyncio.TimeoutError:
                return None

        with patch("app.core.scheduler.DACCApiSource") as mock_source_class, \
             patch("app.core.scheduler.extract_timestamp", return_value=datetime(2026, 5, 5, 12, 30, 0)), \
             patch("app.core.scheduler.RadarImageRepository") as mock_repo_class, \
             patch("app.core.scheduler.RadarPipeline") as mock_pipeline_class, \
             patch("app.core.scheduler.settings") as mock_settings, \
             patch("app.core.scheduler.async_session") as mock_async_session, \
             patch("app.core.scheduler.crop_margins", side_effect=lambda img: img), \
             patch("app.core.scheduler.DACCScheduler._detect_invalid_image", return_value=None), \
             patch("app.core.scheduler.asyncio.wait_for", side_effect=mock_wait):
             

            # Configurar mocks para happy path en cada tick
            mock_source = MagicMock()
            temp_file = tmp_path / "dacc_latest.gif"
            Image.effect_noise((300, 300), 100).convert("RGB").save(temp_file)
            mock_source.fetch = AsyncMock(return_value=temp_file)
            mock_source_class.return_value = mock_source

            mock_repo = MagicMock()
            mock_repo.get_by_timestamp = AsyncMock(return_value=None)  # No duplicados
            mock_repo_class.return_value = mock_repo

            # Mock de async_session como gestor de contexto async
            mock_session_ctx = MagicMock()
            mock_session_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_async_session.return_value = mock_session_ctx

            mock_pipeline = MagicMock()
            mock_pipeline.process = AsyncMock(return_value=tmp_path / "output.tif")
            mock_pipeline_class.return_value = mock_pipeline

            mock_settings.DACC_LOOP_INTERVAL_SECONDS = 120
            mock_settings.geotiff_storage_path = str(tmp_path)

            await scheduler.start()
            await scheduler._task  # Esperar a que termine

            # Verificar que corrió 3 ticks
            assert tick_count == 3
            assert scheduler.total_processed_this_session == 3
            assert scheduler.total_skipped_duplicates == 0
            assert scheduler.total_discarded_invalid == 0

    @pytest.mark.asyncio
    async def test_pipeline_creates_dynamic_folders(self, geo_loader, tmp_path):
        """Pipeline procesa imagen y crea carpetas dacc_api/YYYY/MM/."""
        from app.processing.services.radar_pipeline import RadarPipeline
        from app.data.repositories.radar_image_repository import RadarImageRepository
        from sqlalchemy.ext.asyncio import AsyncSession
        from unittest.mock import AsyncMock

        # Crear imagen sintética
        image = Image.new("RGB", (400, 300), color=(255, 255, 255))
        temp_file = tmp_path / "input.gif"
        image.save(temp_file)

        # Timestamp para carpeta 2026/05
        timestamp = datetime(2026, 5, 5, 12, 30, 0)

        # Mock session y repo
        mock_session = AsyncMock(spec=AsyncSession)
        mock_repo = MagicMock(spec=RadarImageRepository)
        mock_repo.get_by_timestamp = AsyncMock(return_value=None)
        mock_repo.save = AsyncMock(return_value=MagicMock())

        with patch("app.processing.services.radar_pipeline.extract_timestamp_from_filename", return_value=None), \
             patch("app.processing.services.radar_pipeline.extract_timestamp", return_value=timestamp), \
             patch("app.processing.services.radar_pipeline.RadarImageRepository", return_value=mock_repo), \
             patch("app.processing.services.radar_pipeline.clean_image"), \
             patch("app.processing.services.radar_pipeline.fill_gaps"), \
             patch("app.processing.services.radar_pipeline.apply_geo_reference"):
            pipeline = RadarPipeline(geo_loader, mock_session, output_dir=tmp_path)

            # Mock los pasos internos para que no fallen
            from app.processing.services.radar_pipeline import clean_image, fill_gaps
            clean_image.return_value = (MagicMock(), MagicMock())
            fill_gaps.return_value = MagicMock()

            output_path = await pipeline.process(
                image_path=temp_file,
                source_type="dacc_api",
                fallback_timestamp=None,
            )

            # Verificar que el path retornado tenga la estructura correcta
            assert "dacc_api/2026/05/san_rafael_050526_123000.tif" in str(output_path)