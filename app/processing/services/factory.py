from pathlib import Path

from app.core.config import settings
from app.processing.services.image_source import ImageSource
from app.processing.services.local_source import LocalSource
from app.processing.services.dacc_api_source import DACCApiSource
from app.processing.services.cloud_bank_source import CloudBankSource


def get_image_source() -> ImageSource:
    match settings.image_source_type:
        case "local":
            source_path = settings.radar_gif_source_path or settings.image_source_path
            return LocalSource(Path(source_path), pattern=settings.radar_gif_pattern)
        case "dacc_api":
            return DACCApiSource()
        case "cloud_bank":
            return CloudBankSource(settings.image_source_url)
        case _:
            raise ValueError(f"Fuente desconocida: {settings.image_source_type}")