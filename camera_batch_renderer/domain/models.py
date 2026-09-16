from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .compat import StrEnum


class Channel(StrEnum):
    BEAUTY = "Beauty"
    ALPHA = "Alpha"
    OBJECT_ID = "ObjectID"


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


@dataclass(frozen=True, slots=True)
class CameraEnvironmentSpec:
    light_collection_name: str | None = None
    light_collection_key: str | None = None
    light_object_keys: tuple[str, ...] | None = None
    world_key: str | None = None
    world_name: str | None = None


@dataclass(frozen=True, slots=True)
class CameraSpec:
    key: str
    display_name: str
    output_name: str
    environment: CameraEnvironmentSpec | None = None


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
    blend_path: Path
    blend_name: str
    output_directory: Path
    scene_name: str
    view_layer_name: str
    frame: int
    cameras: tuple[CameraSpec, ...]
    channels: tuple[Channel, ...]
    settings: RenderSettings


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
