from __future__ import annotations

import json
import os
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class AtomicJsonWriter:
    def __init__(self, path: Path, *, temporary_directory: Path | None = None):
        self.path = path
        self.temporary_directory = temporary_directory

    def write(self, payload: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_directory = self.temporary_directory or self.path.parent
        temporary_directory.mkdir(parents=True, exist_ok=True)
        temporary = temporary_directory / f".{self.path.name}.{uuid.uuid4().hex}.tmp"
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
