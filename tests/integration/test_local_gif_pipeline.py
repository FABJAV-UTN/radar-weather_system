"""
Tests de integración del pipeline con GIFs locales (LocalSource).

Usa GIFs reales del directorio local (/home/fabio/Descargas/radar_mendoza/radar)
en lugar de depender del servidor DACC API online.

Valida que:
1. LocalSource.list_available() lista correctamente los GIFs disponibles
2. Los timestamps se extraen correctamente del nombre del archivo
   - Si el nombre tiene fecha (ej: radar_20260130_1344_29.gif) → timestamp del nombre
   - Si el nombre NO tiene fecha (ej: latest.gif) → fallback a OCR sobre el contenido
3. RadarPipeline.process_local() procesa cada GIF sin errores
4. Se detectan y reportan duplicados, imágenes inválidas, etc.
"""

import asyncio
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from app.processing.services.local_source import LocalSource, extract_timestamp_from_filename
from app.processing.services.radar_pipeline import RadarPipeline
from app.processing.algorithms.georeferencer import GeoReferenceLoader
from app.processing.algorithms.timestamp_extractor import extract_timestamp

# Configurar logging para ver los resultados del test
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Path al directorio con GIFs reales
LOCAL_RADAR_PATH = Path("/home/fabio/Descargas/radar_mendoza/radar (Copiar)")


class TestLocalGifPipeline:
    """Tests de integración del pipeline con GIFs locales."""

    @pytest.fixture
    def geo_loader(self, tmp_path: Path):
        """GeoReferenceLoader con placeholders para tests."""
        loader = GeoReferenceLoader(datotif_dir=tmp_path)
        loader.load_all()  # Usa placeholders
        return loader

    @pytest.mark.asyncio
    async def test_list_available_local_gifs(self):
        """Test 1: LocalSource lista correctamente los GIFs disponibles."""
        if not LOCAL_RADAR_PATH.exists():
            pytest.skip(f"Directorio de prueba no encontrado: {LOCAL_RADAR_PATH}")

        logger.info("=" * 80)
        logger.info("TEST 1: Listando GIFs locales disponibles")
        logger.info("=" * 80)

        source = LocalSource(base_path=LOCAL_RADAR_PATH, pattern="*.gif")
        entries = await source.list_available(date_from="", date_to="")

        logger.info(f"Total de GIFs encontrados: {len(entries)}")

        assert len(entries) > 0, "No se encontraron GIFs locales"

        for i, entry in enumerate(entries, 1):
            logger.info(
                f"  {i}. {entry.filename:50s} → timestamp: {entry.timestamp}"
            )
            assert entry.filename is not None
            assert entry.file_path is not None

    @pytest.mark.asyncio
    async def test_timestamp_extraction_from_filenames(self):
        """
        Test 2: Extrae timestamps — del nombre del archivo o por OCR como fallback.

        Para archivos con fecha en el nombre (radar_YYYYMMDD_HHMM_SS.gif):
            → usa timestamp del nombre (LocalSource)

        Para archivos sin fecha en el nombre (latest.gif, latest2.gif, etc.):
            → fallback a OCR sobre el contenido del GIF (igual que DACCScheduler._tick())
        """
        if not LOCAL_RADAR_PATH.exists():
            pytest.skip(f"Directorio de prueba no encontrado: {LOCAL_RADAR_PATH}")

        logger.info("=" * 80)
        logger.info("TEST 2: Extrayendo timestamps (nombre o OCR como fallback)")
        logger.info("=" * 80)

        source = LocalSource(base_path=LOCAL_RADAR_PATH, pattern="*.gif")
        entries = await source.list_available(date_from="", date_to="")

        valid_count = 0
        invalid_count = 0

        for entry in entries:
            ts = entry.timestamp

            if ts is not None:
                # Timestamp extraído del nombre del archivo
                valid_count += 1
                logger.info(
                    f"  ✓ {entry.filename:50s} → {ts.isoformat()} [nombre]"
                )
            else:
                # Nombre sin fecha → intentar OCR sobre el contenido (flujo DACC)
                try:
                    img = Image.open(entry.file_path)
                    ts = extract_timestamp(img)
                except Exception as e:
                    logger.warning(
                        f"  ✗ {entry.filename:50s} → ERROR abriendo imagen: {e}"
                    )
                    invalid_count += 1
                    continue

                if ts is not None:
                    valid_count += 1
                    logger.info(
                        f"  ✓ {entry.filename:50s} → {ts.isoformat()} [OCR]"
                    )
                else:
                    invalid_count += 1
                    logger.warning(
                        f"  ✗ {entry.filename:50s} → NO SE PUDO EXTRAER TIMESTAMP"
                    )

        logger.info(
            f"Resumen: {valid_count} válidos, {invalid_count} inválidos"
        )
        assert valid_count > 0, "Ningún timestamp pudo ser extraído"

    @pytest.mark.asyncio
    async def test_process_local_gifs_full_pipeline(self, geo_loader, tmp_path: Path):
        """
        Test 3: Pipeline procesa cada GIF local correctamente.

        Simula el flujo completo del scheduler:
        - LocalSource.list_available() → lista GIFs
        - RadarPipeline.process_local() → procesa cada uno
        - Loggea: nombre, timestamp, resultado (procesado/skipeado/descartado)
        """
        if not LOCAL_RADAR_PATH.exists():
            pytest.skip(f"Directorio de prueba no encontrado: {LOCAL_RADAR_PATH}")

        logger.info("=" * 80)
        logger.info("TEST 3: Pipeline completo con GIFs locales")
        logger.info(f"Output directory: {tmp_path}")
        logger.info("=" * 80)

        # Preparar LocalSource
        source = LocalSource(base_path=LOCAL_RADAR_PATH, pattern="*.gif")

        # Preparar mock session y repo
        mock_session = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.get_by_timestamp = AsyncMock(return_value=None)  # Sin duplicados
        mock_repo.save = AsyncMock(return_value=MagicMock())

        # Preparar pipeline
        with patch("app.processing.services.radar_pipeline.RadarImageRepository", return_value=mock_repo), \
             patch("app.processing.services.radar_pipeline.clean_image") as mock_clean, \
             patch("app.processing.services.radar_pipeline.fill_gaps") as mock_fill, \
             patch("app.processing.services.radar_pipeline.apply_geo_reference") as mock_geo:

            # Mock los pasos de procesamiento
            mock_clean.return_value = (MagicMock(), MagicMock())
            mock_fill.return_value = MagicMock()

            pipeline = RadarPipeline(
                geo_loader=geo_loader,
                session=mock_session,
                output_dir=tmp_path,
                location="san_rafael",
            )

            # Listar y procesar cada GIF
            entries = await source.list_available(date_from="", date_to="")
            logger.info(f"Procesando {len(entries)} GIF(s)...\n")

            results = {
                "processed": [],
                "skipped": [],
                "discarded": [],
            }

            for i, entry in enumerate(entries, 1):
                logger.info(f"[{i}/{len(entries)}] Procesando: {entry.filename}")

                # Obtener timestamp: del nombre o por OCR
                ts = entry.timestamp
                if ts is None:
                    try:
                        img = Image.open(entry.file_path)
                        ts = extract_timestamp(img)
                    except Exception as e:
                        logger.warning(f"  → DESCARTADO: Error abriendo imagen: {e}")
                        results["discarded"].append(
                            {"filename": entry.filename, "reason": f"open_error: {e}"}
                        )
                        continue

                if ts is None:
                    logger.warning(f"  → DESCARTADO: No se pudo extraer timestamp")
                    results["discarded"].append(
                        {"filename": entry.filename, "reason": "invalid_timestamp"}
                    )
                    continue

                logger.info(f"  Timestamp extraído: {ts.isoformat()}")

                try:
                    output_path = await pipeline.process_local(entry.file_path)

                    if output_path is None:
                        is_duplicate = await mock_repo.get_by_timestamp(
                            "san_rafael", ts
                        )
                        if is_duplicate:
                            logger.info(f"  → SKIPEADO: Duplicado detectado")
                            results["skipped"].append(
                                {"filename": entry.filename, "timestamp": ts.isoformat()}
                            )
                        else:
                            logger.error(f"  → DESCARTADO: Error en el procesamiento")
                            results["discarded"].append(
                                {"filename": entry.filename, "reason": "processing_error"}
                            )
                    else:
                        logger.info(f"  → PROCESADO: {output_path.name}")
                        results["processed"].append(
                            {
                                "filename": entry.filename,
                                "timestamp": ts.isoformat(),
                                "output": str(output_path),
                            }
                        )

                except Exception as e:
                    logger.error(f"  → DESCARTADO: Excepción: {e}", exc_info=True)
                    results["discarded"].append(
                        {"filename": entry.filename, "reason": f"exception: {str(e)}"}
                    )

                logger.info("")

            # Reportar resumen
            logger.info("=" * 80)
            logger.info("RESUMEN DEL PROCESAMIENTO")
            logger.info("=" * 80)
            logger.info(f"Procesados:   {len(results['processed'])}")
            logger.info(f"Skipeados:    {len(results['skipped'])}")
            logger.info(f"Descartados:  {len(results['discarded'])}")
            logger.info(f"Total:        {len(entries)}")

            assert (
                len(results["processed"]) > 0 or len(results["skipped"]) > 0
            ), "Ningún GIF pudo procesarse o skippearse correctamente"

    @pytest.mark.asyncio
    async def test_timestamp_extraction_patterns(self):
        """Test 4: Valida que los patrones de timestamp funcionen correctamente."""
        logger.info("=" * 80)
        logger.info("TEST 4: Validando patrones de extracción de timestamp")
        logger.info("=" * 80)

        test_cases = [
            ("radar_20260130_1344_29.gif", datetime),
            ("radar_20260101_0000_00.gif", datetime),
            ("san_rafael_20260605_203000.gif", datetime),
            ("2026-05-04 20-30-00.gif", datetime),
            ("20260504-203000.gif", datetime),
            ("invalid_format_xyz.gif", type(None)),
        ]

        for filename, expected_type in test_cases:
            result = extract_timestamp_from_filename(filename)
            if expected_type == datetime:
                assert isinstance(
                    result, datetime
                ), f"Failed for {filename}: got {result}"
                logger.info(f"  ✓ {filename:35s} → {result.isoformat()}")
            else:
                assert (
                    result is None
                ), f"Expected None for {filename}, got {result}"
                logger.info(f"  ✓ {filename:35s} → (no timestamp)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])