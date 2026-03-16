from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(slots=True)
class VideoReference:
    provider: str
    path: str


class StorageProvider(Protocol):
    def store_video(
        self,
        *,
        execution_id: str,
        filename: str | None,
        source_path: str | Path,
        content_type: str | None,
    ) -> VideoReference: ...
