from __future__ import annotations

import ctypes
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

WORK_DIRECTORY_NAME = ".render-all-cameras-work"


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
    shutil.rmtree(working_directory, ignore_errors=True)
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
    shutil.rmtree(allocation.working_directory, ignore_errors=True)
