from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path

from .models import CameraSpec, Channel, RenderSettings

_NATURAL_PARTS = re.compile(r"(\d+)")
_INVALID = re.compile(r"[<>:\"/\\|?*\x00-\x1f]")
_WHITESPACE = re.compile(r"\s+")
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

OUTPUT_DIRECTORY_NAME = "SekerRenderAllCameras"


def natural_key(value: str) -> tuple[object, ...]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return tuple(int(part) if part.isdigit() else part for part in _NATURAL_PARTS.split(normalized))


def sanitize_component(value: str, *, fallback: str = "Unnamed", max_length: int = 80) -> str:
    value = unicodedata.normalize("NFC", value)
    value = _INVALID.sub("_", value)
    value = _WHITESPACE.sub("_", value).strip(" ._")
    if not value:
        value = fallback
    if value.split(".", 1)[0].upper() in _WINDOWS_RESERVED:
        value = f"_{value}"
    return value[:max_length].rstrip(" ._") or fallback


def camera_specs(cameras: Iterable[tuple[str, str]]) -> tuple[CameraSpec, ...]:
    """Build stable, collision-free output names from ``(stable_key, display_name)`` pairs."""
    ordered = sorted(
        cameras,
        key=lambda item: (
            natural_key(sanitize_component(item[1], fallback="Camera")),
            item[0].casefold(),
        ),
    )
    counts: dict[str, int] = {}
    result: list[CameraSpec] = []
    for key, display_name in ordered:
        base = sanitize_component(display_name, fallback="Camera")
        collision_key = base.casefold()
        counts[collision_key] = counts.get(collision_key, 0) + 1
        suffix = "" if counts[collision_key] == 1 else f"_{counts[collision_key]:02d}"
        result.append(CameraSpec(key=key, display_name=display_name, output_name=f"{base}{suffix}"))
    return tuple(result)


def output_filename(
    *,
    blend_name: str,
    camera_name: str,
    channel: Channel,
    settings: RenderSettings,
) -> str:
    safe_blend = sanitize_component(blend_name, fallback="Blend", max_length=64)
    safe_camera = sanitize_component(camera_name, fallback="Camera", max_length=64)
    dimensions = f"{settings.width}x{settings.height}"
    if channel is Channel.BEAUTY:
        pieces = [
            safe_blend,
            safe_camera,
            channel.value,
            dimensions,
            settings.engine_label,
        ]
        if settings.samples is not None:
            pieces.append(f"S{settings.samples}")
        extension = settings.file_extension
    elif channel is Channel.ALPHA:
        pieces = [safe_blend, safe_camera, channel.value, dimensions]
        extension = ".png"
    elif channel is Channel.OBJECT_ID:
        pieces = [safe_blend, safe_camera, channel.value, dimensions, "Object"]
        extension = ".png"
    else:
        pieces = [safe_blend, safe_camera, channel.value, dimensions, "Material"]
        extension = ".png"
    if not extension.startswith("."):
        extension = f".{extension}"
    return "_".join(pieces) + extension.lower()


def fit_path(directory: Path, filename: str, *, max_path: int = 240) -> str:
    """Shorten the stem deterministically while preserving suffix and extension."""
    available = max_path - len(str(directory)) - 1
    if len(filename) <= available:
        return filename
    suffix = Path(filename).suffix
    stem = Path(filename).stem
    if available <= len(suffix) + 8:
        raise ValueError("output directory leaves no safe filename budget")
    return stem[: available - len(suffix)].rstrip(" ._") + suffix
