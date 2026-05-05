from pathlib import Path

from app.processing.services.image_source import ImageSource


class CloudBankSource(ImageSource):
    def __init__(self, api_url: str):
        self.api_url = api_url

    async def fetch(self, identifier: str, destination: Path) -> Path:
        # TODO: Implementar cuando tengas la API del banco
        raise NotImplementedError("Cloud bank no implementado aún")

    async def list_available(self, date_from: str, date_to: str) -> list[str]:
        # TODO: Implementar
        return []