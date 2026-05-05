from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ImageSourceEntry:
    file_path: Path | str
    filename: str
    timestamp: datetime | None
    source_type: str


class ImageSource(Protocol):
    async def fetch(self, identifier: str, destination: Path | None = None) -> Path: ...
    async def list_available(self, date_from: str, date_to: str) -> list[ImageSourceEntry]: ...