from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .manifest import AtomicJsonWriter


class DiagnosticJournal:
    """Durable observation only: never changes or owns batch state."""

    def __init__(self, directory: Path, environment: dict[str, Any]):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        self.path = directory / f"Render-{stamp}-{uuid4().hex[:12]}.json"
        self.writer = AtomicJsonWriter(self.path)
        self.started = time.monotonic()
        self.last_write = float("-inf")
        self.write_error = ""
        self.payload: dict[str, Any] = {
            "schema_version": 1,
            "environment": environment,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "events": [],
            "errors": [],
            "note": "An unfinished report is a last checkpoint, not proof of a crash cause.",
        }

    def record(self, event: str, *, heartbeat: bool = False, **details: Any) -> bool:
        now = time.monotonic()
        if heartbeat and now - self.last_write < 5.0:
            return not self.write_error
        entry = {
            "event": event,
            "at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(now - self.started, 3),
            **details,
        }
        self.payload["last_checkpoint"] = entry
        self.payload["events"] = (self.payload["events"] + [entry])[-128:]
        if details.get("error"):
            self.payload["errors"] = (self.payload["errors"] + [entry])[-32:]
        self.last_write = now
        try:
            self.writer.write(self.payload)
        except Exception as exc:
            self.write_error = str(exc)
            print(f"Render diagnostic write failed: {exc}", flush=True)
            return False
        self.write_error = ""
        return True
