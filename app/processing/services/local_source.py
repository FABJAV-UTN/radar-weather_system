from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.processing.services.image_source import ImageSource, ImageSourceEntry


@dataclass(frozen=True)
class LocalRadarImage(ImageSourceEntry):
    file_path: Path
    filename: str
    timestamp: datetime | None
    source_type: str = "local_bank"


class LocalSource(ImageSource):
    def __init__(self, base_path: Path, pattern: str = "*.png"):
        self.base_path = base_path
        self.pattern = pattern

    async def fetch(self, identifier: str, destination: Path | None = None) -> Path:
        source = self.base_path / identifier
        if not source.exists():
            raise FileNotFoundError(f"Imagen no encontrada: {source}")
        return source

    async def list_available(self, date_from: str, date_to: str) -> list[ImageSourceEntry]:
        if not self.base_path.exists():
            raise FileNotFoundError(f"Carpeta de radar no encontrada: {self.base_path}")

        files = [file_path for file_path in self.base_path.glob(self.pattern) if file_path.is_file()]
        entries: list[ImageSourceEntry] = []
        for file_path in files:
            timestamp = extract_timestamp_from_filename(file_path.name)
            entries.append(
                LocalRadarImage(
                    file_path=file_path,
                    filename=file_path.name,
                    timestamp=timestamp,
                )
            )

        entries.sort(key=lambda entry: (entry.timestamp is None, entry.timestamp or datetime.max, entry.filename))
        return entries


def extract_timestamp_from_filename(filename: str) -> datetime | None:
    stem = Path(filename).stem
    patterns = [
        r"(?P<year>\d{4})[-_]? ?(?P<month>\d{2})[-_]? ?(?P<day>\d{2})[_\- ]+(?P<hour>\d{2})[-_]? ?(?P<minute>\d{2})(?:[-_]? ?(?P<second>\d{2}))?",
        r"(?P<day>\d{2})[-_]? ?(?P<month>\d{2})[-_]? ?(?P<year>\d{4})[_\- ]+(?P<hour>\d{2})[-_]? ?(?P<minute>\d{2})(?:[-_]? ?(?P<second>\d{2}))?",
        r"(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})[_\- ]?(?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2})",
        r"(?P<day>\d{2})(?P<month>\d{2})(?P<year>\d{4})[_\- ]?(?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, stem)
        if not match:
            continue

        values = match.groupdict()
        try:
            year = int(values.get("year", 0))
            month = int(values.get("month", 0))
            day = int(values.get("day", 0))
            hour = int(values.get("hour", 0))
            minute = int(values.get("minute", 0))
            second = int(values.get("second") or 0)
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            continue

    return None
