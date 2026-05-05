from typing import Protocol
from pathlib import Path


class ImageSource(Protocol):
    async def fetch(self, identifier: str, destination: Path) -> Path: ...
    async def list_available(self, date_from: str, date_to: str) -> list[str]: ...