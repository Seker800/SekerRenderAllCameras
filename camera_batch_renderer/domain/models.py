from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Channel(StrEnum):
    BEAUTY = "Beauty"
    ALPHA = "Alpha"
    OBJECT_ID = "ObjectID"


class ConflictPolicy(StrEnum):
    NEXT_BATCH = "NEXT_BATCH"
    SKIP = "SKIP"
    OVERWRITE = "OVERWRITE"


class BatchStatus(StrEnum):
    IDLE = "idle"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ResultStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED_EXISTING = "skipped_existing"


@dataclass(frozen=True, slots=True)
class CameraSpec:
    key: str
    display_name: str
    output_name: str


@dataclass(frozen=True, slots=True)
class RenderSettings:
    engine: str
    engine_label: str
    width: int
    height: int
    file_format: str
    file_extension: str
    samples: int | None = None
    film_transparent: bool = False


@dataclass(frozen=True, slots=True)
class RenderPlan:
    batch_number: int
    batch_label: str
    blend_path: Path
    blend_name: str
    output_directory: Path
    scene_name: str
    view_layer_name: str
    frame: int
    cameras: tuple[CameraSpec, ...]
    channels: tuple[Channel, ...]
    settings: RenderSettings
    conflict_policy: ConflictPolicy


@dataclass(frozen=True, slots=True)
class ChannelResult:
    camera_key: str
    camera_name: str
    channel: Channel
    path: Path
    status: ResultStatus
    elapsed_seconds: float = 0.0
    error: str | None = None


@dataclass(frozen=True, slots=True)
class JobProgress:
    status: BatchStatus
    camera_index: int
    camera_count: int
    current_camera: str | None
    current_channel: Channel | None
    cancel_requested: bool
    results: tuple[ChannelResult, ...] = field(default_factory=tuple)
    error: str | None = None
