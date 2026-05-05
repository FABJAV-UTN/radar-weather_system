from pathlib import Path

import httpx

from app.processing.services.image_source import ImageSource, ImageSourceEntry


class DACCApiSource(ImageSource):
    URL = "https://www2.contingencias.mendoza.gov.ar/radar/latest.gif"

    async def fetch(self, identifier: str, destination: Path | None = None) -> Path:
        if destination is None:
            raise ValueError("Destination is required for DACC API fetch")
        async with httpx.AsyncClient() as client:
            response = await client.get(self.URL)
            response.raise_for_status()
            destination.write_bytes(response.content)
            return destination

    async def list_available(self, date_from: str, date_to: str) -> list[ImageSourceEntry]:
        # La API DACC solo tiene "latest", no histórico listable
        return [
            ImageSourceEntry(
                file_path=self.URL,
                filename="latest.gif",
                timestamp=None,
                source_type="dacc_api",
            )
        ]