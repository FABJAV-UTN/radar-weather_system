from pathlib import Path
import shutil

from app.processing.services.image_source import ImageSource


class LocalSource(ImageSource):
    def __init__(self, base_path: Path):
        self.base_path = base_path

    async def fetch(self, filename: str, destination: Path) -> Path:
        source = self.base_path / filename
        if not source.exists():
            raise FileNotFoundError(f"Imagen no encontrada: {source}")
        shutil.copy2(source, destination)
        return destination

    async def list_available(self, date_from: str, date_to: str) -> list[str]:
        # Por ahora, listar todos los archivos
        return [f.name for f in self.base_path.iterdir() if f.is_file()]