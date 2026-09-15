from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class OutputAllocation:
    directory: Path
    marker: Path


def prepare_output_directory(directory: Path) -> OutputAllocation:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".incomplete").unlink(missing_ok=True)
    marker = directory / ".inprogress"
    marker.write_text("in_progress\n", encoding="utf-8")
    return OutputAllocation(directory=directory, marker=marker)


def mark_incomplete(allocation: OutputAllocation) -> Path:
    target = allocation.directory / ".incomplete"
    if allocation.marker.exists():
        allocation.marker.replace(target)
    return target


def mark_complete(allocation: OutputAllocation) -> None:
    allocation.marker.unlink(missing_ok=True)
    (allocation.directory / ".incomplete").unlink(missing_ok=True)
