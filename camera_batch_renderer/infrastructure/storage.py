from __future__ import annotations

import ctypes
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

WORK_DIRECTORY_NAME = ".render-all-cameras-work"


def _remove_work_directory(directory: Path) -> None:
    """Retry short Windows sharing locks, never hide a permanent cleanup error."""
    delays = (0.0, 0.05, 0.1, 0.2)
    for attempt, delay in enumerate(delays):
        if delay:
            time.sleep(delay)
        try:
            shutil.rmtree(directory)
            return
        except FileNotFoundError:
            if not directory.exists():
                return
            raise
        except OSError as exc:
            if getattr(exc, "winerror", None) not in {5, 32, 33, 145}:
                raise
            if attempt == len(delays) - 1:
                raise OSError(
                    "Cannot clean temporary render directory; "
                    f"a file may still be in use: {directory}"
                ) from exc


@dataclass(frozen=True, slots=True)
class OutputAllocation:
    directory: Path
    working_directory: Path
    staging_directory: Path
    marker: Path


def _hide_on_windows(directory: Path) -> None:
    if os.name != "nt":
        return
    hidden = 0x2
    attributes = ctypes.windll.kernel32.GetFileAttributesW(str(directory))
    if attributes == -1 or not ctypes.windll.kernel32.SetFileAttributesW(
        str(directory), attributes | hidden
    ):
        raise OSError(f"Could not hide working directory: {directory}")


def prepare_output_directory(directory: Path) -> OutputAllocation:
    directory.mkdir(parents=True, exist_ok=True)
    working_directory = directory / WORK_DIRECTORY_NAME
    _remove_work_directory(working_directory)
    working_directory.mkdir()
    _hide_on_windows(working_directory)
    staging_directory = working_directory / "staging"
    staging_directory.mkdir()
    marker = working_directory / ".inprogress"
    marker.write_text("in_progress\n", encoding="utf-8")
    return OutputAllocation(
        directory=directory,
        working_directory=working_directory,
        staging_directory=staging_directory,
        marker=marker,
    )


def mark_incomplete(allocation: OutputAllocation) -> Path:
    target = allocation.working_directory / ".incomplete"
    if allocation.marker.exists():
        allocation.marker.replace(target)
    return target


def mark_complete(allocation: OutputAllocation) -> None:
    _remove_work_directory(allocation.working_directory)
