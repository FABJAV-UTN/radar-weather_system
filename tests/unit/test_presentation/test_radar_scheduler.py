"""
Tests unitarios de los endpoints DACC del scheduler.

Mockean FastAPI Request y el scheduler para probar solo la lógica de endpoints.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app


class TestDACCProcessEndpoint:
    """Tests del endpoint POST /api/v1/radar/process-dacc."""

    def test_post_process_dacc_starts_scheduler(self):
        """POST inicia scheduler y retorna started."""
        client = TestClient(app)

        with patch("app.presentation.api.v1.radar.DACCScheduler") as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler.is_running.return_value = False
            mock_scheduler.start = AsyncMock()
            mock_scheduler_class.return_value = mock_scheduler

            # Simular scheduler en app.state
            app.state.dacc_scheduler = mock_scheduler

            response = client.post("/api/v1/radar/process-dacc")
            assert response.status_code == 200
            assert response.json() == {"status": "started"}
            mock_scheduler.start.assert_called_once()

    def test_post_process_dacc_already_running_returns_409(self):
        """Si scheduler ya corre, retorna 409."""
        client = TestClient(app)

        with patch("app.presentation.api.v1.radar.DACCScheduler") as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler.is_running.return_value = True
            mock_scheduler_class.return_value = mock_scheduler

            app.state.dacc_scheduler = mock_scheduler

            response = client.post("/api/v1/radar/process-dacc")
            assert response.status_code == 409
            assert "ya está activo" in response.json()["detail"]


class TestDACCStopEndpoint:
    """Tests del endpoint POST /api/v1/radar/process-dacc/stop."""

    def test_post_stop_stops_scheduler(self):
        """POST detiene scheduler y retorna stopped."""
        client = TestClient(app)

        with patch("app.presentation.api.v1.radar.DACCScheduler") as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler.is_running.return_value = True
            mock_scheduler.stop = AsyncMock()
            mock_scheduler_class.return_value = mock_scheduler

            app.state.dacc_scheduler = mock_scheduler

            response = client.post("/api/v1/radar/process-dacc/stop")
            assert response.status_code == 200
            assert response.json() == {"status": "stopped"}
            mock_scheduler.stop.assert_called_once()

    def test_post_stop_not_running_returns_404(self):
        """Si scheduler no corre, retorna 404."""
        client = TestClient(app)

        with patch("app.presentation.api.v1.radar.DACCScheduler") as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler.is_running.return_value = False
            mock_scheduler_class.return_value = mock_scheduler

            app.state.dacc_scheduler = mock_scheduler

            response = client.post("/api/v1/radar/process-dacc/stop")
            assert response.status_code == 404
            assert "no está activo" in response.json()["detail"]


class TestDACCStatusEndpoint:
    """Tests del endpoint GET /api/v1/radar/process-dacc/status."""

    def test_get_status_returns_full_json(self):
        """GET retorna JSON completo con métricas."""
        client = TestClient(app)

        with patch("app.presentation.api.v1.radar.DACCScheduler") as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler.get_status.return_value = {
                "is_running": True,
                "started_at": "2026-05-05T12:00:00-03:00",
                "last_download_at": "2026-05-05T12:02:00-03:00",
                "last_image_timestamp": "2026-05-05T12:01:00-03:00",
                "total_processed_this_session": 5,
                "total_skipped_duplicates": 2,
                "total_discarded_invalid": 1,
                "next_run_in_seconds": 58,
            }
            mock_scheduler_class.return_value = mock_scheduler

            app.state.dacc_scheduler = mock_scheduler

            response = client.get("/api/v1/radar/process-dacc/status")
            assert response.status_code == 200
            data = response.json()
            assert data["is_running"] is True
            assert data["total_processed_this_session"] == 5
            assert data["total_skipped_duplicates"] == 2
            assert data["total_discarded_invalid"] == 1
            assert data["next_run_in_seconds"] == 58