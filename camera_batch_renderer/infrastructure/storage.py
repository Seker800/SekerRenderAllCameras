from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..domain.naming import format_batch


@dataclass(frozen=True, slots=True)
class BatchAllocation:
    number: int
    label: str
    directory: Path
    marker: Path


def find_next_batch(root: Path, start: int = 1) -> int:
    if start < 0:
        raise ValueError("start must be non-negative")
    number = start
    while (root / format_batch(number)).exists():
        number += 1
    return number


def allocate_batch(root: Path, start: int = 1) -> BatchAllocation:
    root.mkdir(parents=True, exist_ok=True)
    number = start
    while True:
        label = format_batch(number)
        directory = root / label
        try:
            directory.mkdir()
        except FileExistsError:
            number += 1
            continue
        marker = directory / ".inprogress"
        marker.write_text("in_progress\n", encoding="utf-8")
        return BatchAllocation(number=number, label=label, directory=directory, marker=marker)


def mark_incomplete(allocation: BatchAllocation) -> Path:
    target = allocation.directory / ".incomplete"
    if allocation.marker.exists():
        allocation.marker.replace(target)
    return target


def mark_complete(allocation: BatchAllocation) -> None:
    allocation.marker.unlink(missing_ok=True)
    (allocation.directory / ".incomplete").unlink(missing_ok=True)
