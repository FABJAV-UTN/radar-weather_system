import asyncio
from pathlib import Path

import pytest

from app.processing.services.cloud_bank_source import CloudBankSource
from app.processing.services.dacc_api_source import DACCApiSource
from app.processing.services.factory import get_image_source
from app.processing.services.local_source import LocalSource
from app.core import config


@pytest.mark.asyncio
async def test_local_source_fetch_and_list_available(tmp_path: Path) -> None:
    source_file = tmp_path / "radar_sample.gif"
    source_file.write_text("fake radar content")

    local_source = LocalSource(tmp_path)
    destination_file = tmp_path / "copied_radar.gif"

    result_path = await local_source.fetch(source_file.name, destination_file)

    assert result_path == destination_file
    assert destination_file.exists()
    assert destination_file.read_text() == "fake radar content"

    available_files = await local_source.list_available("2026-01-01", "2026-01-31")
    assert source_file.name in available_files


@pytest.mark.asyncio
async def test_local_source_fetch_missing_file_raises(tmp_path: Path) -> None:
    local_source = LocalSource(tmp_path)
    missing_file = "does_not_exist.gif"
    destination_file = tmp_path / "out.gif"

    with pytest.raises(FileNotFoundError):
        await local_source.fetch(missing_file, destination_file)


@pytest.mark.asyncio
async def test_cloud_bank_source_unimplemented_methods() -> None:
    cloud_source = CloudBankSource("https://example.com")

    with pytest.raises(NotImplementedError):
        await cloud_source.fetch("latest.gif", Path("/tmp/out.gif"))

    available_files = await cloud_source.list_available("2026-01-01", "2026-01-31")
    assert available_files == []


def test_factory_returns_local_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config.settings, "image_source_type", "local")
    monkeypatch.setattr(config.settings, "image_source_path", str(tmp_path))

    source = get_image_source()
    assert isinstance(source, LocalSource)


def test_factory_raises_for_unknown_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.settings, "image_source_type", "unknown_source")

    with pytest.raises(ValueError, match="Fuente desconocida"):
        get_image_source()
