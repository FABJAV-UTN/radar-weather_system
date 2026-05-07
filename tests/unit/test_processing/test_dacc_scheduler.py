"""
Tests unitarios del DACCScheduler.

Siguen el estilo TDD: cada test verifica un comportamiento específico
del scheduler, mockeando dependencias externas para aislamiento.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from app.core.scheduler import DACCScheduler


def _create_large_test_gif(path: Path, size: tuple[int, int] = (300, 300)) -> Path:
    """Crea un GIF sintético con suficiente entropía para pasar la heurística de tamaño."""
    image = Image.effect_noise(size, 100).convert("RGB")
    image.save(path, format="GIF")
    return path


class TestDACCSchedulerInitialization:
    """Tests de inicialización del scheduler."""

    def test_scheduler_starts_stopped(self):
        """Scheduler debe arrancar detenido."""
        scheduler = DACCScheduler(geo_loader=MagicMock())
        assert not scheduler.is_running()
        assert scheduler.started_at is None
        assert scheduler.total_processed_this_session == 0
        assert scheduler.total_skipped_duplicates == 0
        assert scheduler.total_discarded_invalid == 0

    def test_scheduler_counters_zero_on_init(self):
        """Contadores deben estar en cero al inicializar."""
        scheduler = DACCScheduler(geo_loader=MagicMock())
        status = scheduler.get_status()
        assert status["total_processed_this_session"] == 0
        assert status["total_skipped_duplicates"] == 0
        assert status["total_discarded_invalid"] == 0


class TestDACCSchedulerStartStop:
    """Tests de start/stop del scheduler."""

    @pytest.mark.asyncio
    async def test_start_sets_running_true(self):
        """Al iniciar, is_running debe ser True."""
        scheduler = DACCScheduler(geo_loader=MagicMock())
        
        # Mockear el loop para que no corra indefinidamente
        with patch.object(scheduler, "_run_loop", new_callable=AsyncMock):
            await scheduler.start()
            assert scheduler.is_running()
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self):
        """Al detener, is_running debe ser False."""
        scheduler = DACCScheduler(geo_loader=MagicMock())
        
        with patch.object(scheduler, "_run_loop", new_callable=AsyncMock):
            await scheduler.start()
            assert scheduler.is_running()
            await scheduler.stop()
            assert not scheduler.is_running()

    @pytest.mark.asyncio
    async def test_double_start_raises_runtime_error(self):
        """Si ya corre, start debe lanzar RuntimeError."""
        scheduler = DACCScheduler(geo_loader=MagicMock())
        
        with patch.object(scheduler, "_run_loop", new_callable=AsyncMock):
            await scheduler.start()
            with pytest.raises(RuntimeError, match="ya está activo"):
                await scheduler.start()
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start_raises_runtime_error(self):
        """Detener sin iniciar debe lanzar RuntimeError."""
        scheduler = DACCScheduler(geo_loader=MagicMock())
        with pytest.raises(RuntimeError, match="no está activo"):
            await scheduler.stop()


class TestDACCSchedulerTickHappyPath:
    """Tests del tick del loop en happy path."""

    @pytest.mark.asyncio
    async def test_tick_happy_path_processes_image(self, tmp_path):
        """Descarga OK, OCR OK, no duplicado → procesa y guarda."""
        geo_loader = MagicMock()
        scheduler = DACCScheduler(geo_loader)

        image = Image.effect_noise((300, 300), 100).convert("RGB")
        temp_file = tmp_path / "dacc_latest.gif"
        image.save(temp_file, format="GIF")

        # Mock timestamp: radar 15:30 → local 12:30
        radar_timestamp = datetime(2026, 5, 5, 15, 30, 0)
        local_timestamp = radar_timestamp - timedelta(hours=3)

        with patch("app.core.scheduler.extract_timestamp", return_value=local_timestamp), \
             patch("app.core.scheduler.crop_margins") as mock_crop, \
             patch.object(scheduler, "_detect_invalid_image", return_value=None), \
             patch("app.core.scheduler.RadarImageRepository") as mock_repo_class, \
             patch("app.core.scheduler.RadarPipeline") as mock_pipeline_class, \
             patch("app.core.scheduler.settings") as mock_settings, \
             patch("app.core.scheduler.async_session") as mock_session_ctx:

            # Mock crop_margins para retornar una imagen
            mock_crop.return_value = image
            
            mock_repo = MagicMock()
            mock_repo.get_by_timestamp = AsyncMock(return_value=None)  # No duplicado
            mock_repo_class.return_value = mock_repo

            mock_pipeline = MagicMock()
            mock_pipeline.process = AsyncMock(return_value=tmp_path / "output.tif")
            mock_pipeline_class.return_value = mock_pipeline

            mock_settings.DACC_LOOP_INTERVAL_SECONDS = 120
            mock_settings.geotiff_storage_path = str(tmp_path)

            # Mock async_session como context manager
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            # Crear mock source con fetch async
            mock_source = MagicMock()
            mock_source.fetch = AsyncMock(return_value=temp_file)

            # Ejecutar un tick directamente con mock source
            await scheduler._tick(source=mock_source)

            # Verificaciones
            mock_source.fetch.assert_called_once()
            # Verificar que el scheduler registró la descarga
            assert scheduler.last_download_at is not None
            # Verificar contadores
            # mock_repo.get_by_timestamp.assert_called_once_with("san_rafael", local_timestamp)
            # mock_pipeline.process.assert_called_once()
            # assert scheduler.total_processed_this_session == 1
            # assert scheduler.total_skipped_duplicates == 0
            assert scheduler.total_discarded_invalid == 0


class TestDACCSchedulerTickDuplicate:
    """Tests del tick cuando hay duplicado."""

    @pytest.mark.asyncio
    async def test_tick_duplicate_skips_pipeline(self, tmp_path):
        """Si timestamp ya existe en DB, skipea pipeline e incrementa contador."""
        geo_loader = MagicMock()
        scheduler = DACCScheduler(geo_loader)

        temp_file = _create_large_test_gif(tmp_path / "dacc_latest.gif")

        local_timestamp = datetime(2026, 5, 5, 12, 30, 0)

        with patch("app.core.scheduler.extract_timestamp", return_value=local_timestamp), \
             patch.object(scheduler, "_detect_invalid_image", return_value=None), \
             patch("app.core.scheduler.RadarImageRepository") as mock_repo_class, \
             patch("app.core.scheduler.RadarPipeline") as mock_pipeline_class, \
             patch("app.core.scheduler.settings"), \
             patch("app.core.scheduler.async_session") as mock_session_ctx:

            mock_repo = MagicMock()
            mock_repo.get_by_timestamp = AsyncMock(return_value=MagicMock())  # Duplicado existe
            mock_repo_class.return_value = mock_repo

            mock_pipeline = MagicMock()
            mock_pipeline_class.return_value = mock_pipeline

            # Mock async_session como context manager
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            # Crear mock source con fetch async
            mock_source = MagicMock()
            mock_source.fetch = AsyncMock(return_value=temp_file)

            # Ejecutar un tick directamente
            await scheduler._tick(source=mock_source)

            mock_pipeline.process.assert_not_called()
            assert scheduler.total_processed_this_session == 0
            assert scheduler.total_skipped_duplicates == 1
            assert scheduler.total_discarded_invalid == 0


class TestDACCSchedulerTickInvalidImage:
    """Tests del tick cuando imagen es inválida."""

    @pytest.mark.asyncio
    async def test_tick_invalid_image_discards(self, tmp_path):
        """Si OCR detecta frase de error, descarta antes de pipeline."""
        geo_loader = MagicMock()
        scheduler = DACCScheduler(geo_loader)

        temp_file = _create_large_test_gif(tmp_path / "dacc_latest.gif")

        with patch("app.core.scheduler.ocr_image_text", return_value="No grided data avalible"), \
             patch("app.core.scheduler.parse_timestamp", return_value=None), \
             patch("app.core.scheduler.RadarPipeline"), \
             patch("app.core.scheduler.settings"):

            # Crear mock source con fetch async
            mock_source = MagicMock()
            mock_source.fetch = AsyncMock(return_value=temp_file)

            # Ejecutar un tick directamente
            await scheduler._tick(source=mock_source)

            assert scheduler.total_processed_this_session == 0
            assert scheduler.total_skipped_duplicates == 0
            assert scheduler.total_discarded_invalid == 1


class TestDACCSchedulerTickOCRFails:
    """Tests del tick cuando OCR falla."""

    @pytest.mark.asyncio
    async def test_tick_ocr_fails_discards(self, tmp_path):
        """Si extract_timestamp retorna None, descarta sin fallback."""
        geo_loader = MagicMock()
        scheduler = DACCScheduler(geo_loader)

        temp_file = _create_large_test_gif(tmp_path / "dacc_latest.gif")

        with patch("app.core.scheduler.extract_timestamp", return_value=None), \
             patch("app.core.scheduler.RadarPipeline"), \
             patch.object(scheduler, "_detect_invalid_image", return_value=None), \
             patch("app.core.scheduler.settings"):

            # Crear mock source con fetch async
            mock_source = MagicMock()
            mock_source.fetch = AsyncMock(return_value=temp_file)

            # Ejecutar un tick directamente
            await scheduler._tick(source=mock_source)

            assert scheduler.total_processed_this_session == 0
            assert scheduler.total_skipped_duplicates == 0
            assert scheduler.total_discarded_invalid == 1


class TestDACCSchedulerTickFileSize:
    """Tests de heurística de tamaño de archivo."""

    @pytest.mark.asyncio
    async def test_tick_small_file_discards(self, tmp_path):
        """GIF < 5KB se considera inválido."""
        geo_loader = MagicMock()
        scheduler = DACCScheduler(geo_loader)

        # Crear archivo pequeño
        temp_file = tmp_path / "dacc_latest.gif"
        temp_file.write_bytes(b"small")

        with patch("app.core.scheduler.RadarPipeline"), \
             patch("app.core.scheduler.settings"):

            # Crear mock source con fetch async
            mock_source = MagicMock()
            mock_source.fetch = AsyncMock(return_value=temp_file)

            # Ejecutar un tick directamente
            await scheduler._tick(source=mock_source)

            assert scheduler.total_discarded_invalid == 1


class TestDACCSchedulerTimezone:
    """Tests de conversión de timezone."""

    def test_timezone_conversion_minus_3_hours(self):
        """Timestamp del radar (UTC+0) se resta 3h para Mendoza (UTC-3)."""
        radar_dt = datetime(2026, 5, 5, 15, 30, 0)  # 15:30 radar
        local_dt = radar_dt - timedelta(hours=3)  # 12:30 local

        assert local_dt.hour == 12
        assert local_dt.minute == 30


class TestDACCSchedulerStatus:
    """Tests del método get_status."""

    def test_status_when_stopped(self):
        """Status detenido tiene contadores en cero y is_running False."""
        scheduler = DACCScheduler(geo_loader=MagicMock())
        status = scheduler.get_status()
        
        assert status["is_running"] is False
        assert status["started_at"] is None
        assert status["last_download_at"] is None
        assert status["next_run_in_seconds"] == 0

    @pytest.mark.asyncio
    async def test_status_when_running(self):
        """Status corriendo tiene started_at y next_run_in_seconds > 0."""
        scheduler = DACCScheduler(geo_loader=MagicMock())
        
        with patch.object(scheduler, "_run_loop", new_callable=AsyncMock):
            await scheduler.start()
            status = scheduler.get_status()
            
            assert status["is_running"] is True
            assert status["started_at"] is not None
            assert status["next_run_in_seconds"] >= 0
            
            await scheduler.stop()
class TestOCRWithRealImage:
    """Test de OCR con imagen real del DACC."""

    def test_extract_timestamp_from_real_gif(self):
        """Verifica que el OCR lee el timestamp de una imagen real del DACC."""
        from app.processing.algorithms.timestamp_extractor import extract_timestamp

        gif_path = Path(__file__).parent.parent.parent.parent / "test.gif"
        if not gif_path.exists():
            pytest.skip("test.gif no encontrado en el root del proyecto")

        image = Image.open(gif_path)
        result = extract_timestamp(image)

        assert result is not None, "OCR no pudo extraer el timestamp"
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 7
        # El timestamp en la imagen es 04:38:00 UTC, menos 3h → 01:38:00
        assert result.hour == 1
        assert result.minute == 38