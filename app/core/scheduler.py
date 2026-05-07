"""Scheduler para el loop continuo de descarga y procesamiento DACC."""

from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

from app.core.config import settings
from app.data.database import async_session
from app.data.repositories.radar_image_repository import RadarImageRepository
from app.processing.algorithms.cropper import crop_margins
from app.processing.algorithms.timestamp_extractor import (
    extract_timestamp,
    ocr_image_text,
    parse_timestamp,
)
from app.processing.services.dacc_api_source import DACCApiSource
from app.processing.services.radar_pipeline import RadarPipeline

logger = logging.getLogger(__name__)
MENDOZA_TZ = timezone(timedelta(hours=-3), name="UTC-3")

ERROR_PHRASES = [
    "no grided data avalible",
    "image not avalible",
    "no data available",
    "service unavailable",
]


class DACCScheduler:
    """Loop background que descarga y procesa imágenes DACC cada intervalo."""

    def __init__(self, geo_loader, location: str = "san_rafael"):
        self.geo_loader = geo_loader
        self.location = location
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self.started_at: datetime | None = None
        self.last_download_at: datetime | None = None
        self.last_image_timestamp: datetime | None = None
        self.total_processed_this_session = 0
        self.total_skipped_duplicates = 0
        self.total_discarded_invalid = 0
        self._next_run_at: datetime | None = None

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.is_running():
            raise RuntimeError("Loop DACC ya está activo")

        self._stop_event = asyncio.Event()
        self.started_at = datetime.now(MENDOZA_TZ)
        self.last_download_at = None
        self.last_image_timestamp = None
        self.total_processed_this_session = 0
        self.total_skipped_duplicates = 0
        self.total_discarded_invalid = 0
        self._next_run_at = self.started_at
        self._task = asyncio.create_task(self._run_loop(), name="dacc_scheduler")

    async def stop(self) -> None:
        if not self.is_running():
            raise RuntimeError("Loop DACC no está activo")

        self._stop_event.set()
        await self._task

    def get_status(self) -> dict[str, object | int | bool | None]:
        now = datetime.now(MENDOZA_TZ)
        next_run_in_seconds = 0
        if self.is_running() and self._next_run_at is not None:
            next_run_in_seconds = max(0, int((self._next_run_at - now).total_seconds()))

        return {
            "is_running": self.is_running(),
            "started_at": self.started_at,
            "last_download_at": self.last_download_at,
            "last_image_timestamp": self._aware_timestamp(self.last_image_timestamp),
            "total_processed_this_session": self.total_processed_this_session,
            "total_skipped_duplicates": self.total_skipped_duplicates,
            "total_discarded_invalid": self.total_discarded_invalid,
            "next_run_in_seconds": next_run_in_seconds,
        }

    async def _tick(self, source: DACCApiSource | None = None) -> None:
        """Ejecuta un ciclo de descarga, validación y procesamiento de imagen DACC."""
        if source is None:
            source = DACCApiSource()

        self.last_download_at = datetime.now(MENDOZA_TZ)
        self._logger().info("DACC loop: descargando...")
        temp_file = Path(tempfile.gettempdir()) / "dacc_latest.gif"

        try:
            fetched_path = await source.fetch("latest.gif", destination=temp_file)

            if not fetched_path.exists() or fetched_path.stat().st_size < 5_000:
                self.total_discarded_invalid += 1
                self._logger().info(
                    "DACC loop: imagen inválida descartada: archivo demasiado pequeño"
                )
                return

            try:
                image = Image.open(fetched_path)
            except Exception as exc:
                self.total_discarded_invalid += 1
                self._logger().info(
                    "DACC loop: imagen inválida descartada: no se pudo abrir el GIF (%s)",
                    exc,
                )
                return

            invalid_reason = self._detect_invalid_image(image)
            if invalid_reason is not None:
                self.total_discarded_invalid += 1
                self._logger().info(
                    "DACC loop: imagen inválida descartada: %s",
                    invalid_reason,
                )
                return

            timestamp = extract_timestamp(image)
            if timestamp is None:
                self.total_discarded_invalid += 1
                self._logger().info("DACC loop: OCR falló, imagen descartada")
                return

            self.last_image_timestamp = timestamp

            async with async_session() as session:
                repo = RadarImageRepository(session)
                existing = await repo.get_by_timestamp(self.location, timestamp)
                if existing is not None:
                    self.total_skipped_duplicates += 1
                    self._logger().info(
                        "DACC loop: duplicado detectado para %s, saltando",
                        timestamp,
                    )
                    return

                pipeline = RadarPipeline(self.geo_loader, session)
                output_path = await pipeline.process_dacc(image_path=fetched_path)

                if output_path is not None:
                    self.total_processed_this_session += 1
                    self._logger().info(
                        "DACC loop: procesada nueva imagen %s en %s",
                        output_path.name,
                        output_path.relative_to(Path(settings.geotiff_storage_path)),
                    )
                else:
                    self._logger().info(
                        "DACC loop: la imagen no generó GeoTIFF y fue descartada"
                    )

        except Exception as exc:
            self._logger().error(
                "DACC loop: error %s, reintentando en 2 min",
                exc,
                exc_info=True,
            )
        finally:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    self._logger().warning(
                        "DACC loop: no se pudo eliminar archivo temporal %s",
                        temp_file,
                    )

    async def _run_loop(self) -> None:
        """Loop principal que ejecuta ticks repetidamente con intervalo configurable."""
        source = DACCApiSource()

        while True:
            
            cycle_start = datetime.now(MENDOZA_TZ)
            await self._tick(source)

            if self._stop_event.is_set():
                break

            elapsed = (datetime.now(MENDOZA_TZ) - cycle_start).total_seconds()
            delay = settings.DACC_LOOP_INTERVAL_SECONDS - elapsed
            self._next_run_at = datetime.now(MENDOZA_TZ) + timedelta(seconds=max(delay, 0))
            if delay > 0:
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
            if self._stop_event.is_set():
                break

    def _detect_invalid_image(self, image: Image.Image) -> str | None:
        raw_text = ocr_image_text(image, psm=6)
        normalized = re.sub(r"\s+", " ", raw_text.lower()).strip()

        for phrase in ERROR_PHRASES:
            if phrase in normalized:
                return phrase

        #if parse_timestamp(normalized) is None:
         #   return "no timestamp válido"

        return None

    def _aware_timestamp(self, timestamp: datetime | None) -> datetime | None:
        if timestamp is None:
            return None
        if timestamp.tzinfo is not None:
            return timestamp
        return timestamp.replace(tzinfo=MENDOZA_TZ)

    def _logger(self) -> logging.Logger:
        return logger
