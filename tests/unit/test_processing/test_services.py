from pathlib import Path

import pytest

from app.processing.services.cloud_bank_source import CloudBankSource
from app.processing.services.dacc_api_source import DACCApiSource
from app.processing.services.factory import get_image_source
from app.processing.services.local_source import LocalSource
from app.core import config


@pytest.mark.asyncio
async def test_local_source_fetch_and_list_available(tmp_path: Path) -> None:
    image_a = tmp_path / "radar_04052026_202900.gif"
    image_b = tmp_path / "RADAR_20260504_203000.gif"
    image_c = tmp_path / "2026-05-04_20-50-00.gif"

    image_a.write_bytes(b"fake radar A")
    image_b.write_bytes(b"fake radar B")
    image_c.write_bytes(b"fake radar C")

    local_source = LocalSource(tmp_path, pattern="*.gif")
    destination_file = tmp_path / "ignored_destination.gif"

    result_path = await local_source.fetch(image_b.name, destination_file)

    assert result_path == image_b
    assert not destination_file.exists()
    assert image_b.exists()

    available = await local_source.list_available("2026-05-04", "2026-05-05")
    assert [item.filename for item in available] == [image_a.name, image_b.name, image_c.name]
    assert [item.source_type for item in available] == ["local_bank", "local_bank", "local_bank"]
    assert [item.file_path for item in available] == [image_a, image_b, image_c]
    assert all(item.timestamp is not None for item in available)


@pytest.mark.asyncio
async def test_local_source_fetch_missing_file_raises(tmp_path: Path) -> None:
    local_source = LocalSource(tmp_path, pattern="*.gif")
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
    assert len(available_files) == 1
    assert available_files[0].source_type == "cloud_bank"


def test_factory_returns_local_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config.settings, "image_source_type", "local")
    monkeypatch.setattr(config.settings, "radar_gif_source_path", str(tmp_path))
    monkeypatch.setattr(config.settings, "image_source_path", "./ignored")

    source = get_image_source()
    assert isinstance(source, LocalSource)


def test_factory_raises_for_unknown_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.settings, "image_source_type", "unknown_source")

    with pytest.raises(ValueError, match="Fuente desconocida"):
        get_image_source()
