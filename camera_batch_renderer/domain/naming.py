from __future__ import annotations

import hashlib
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
    if len(value) > max_length:
        digest = hashlib.blake2s(value.encode("utf-8"), digest_size=8).hexdigest()
        value = (
            f"{value[:max_length - 17]}_{digest}" if max_length > 17 else digest[:max_length]
        )
    return value.rstrip(" ._") or fallback


def camera_specs(cameras: Iterable[tuple[str, str]]) -> tuple[CameraSpec, ...]:
    """Build stable, collision-free output names from ``(stable_key, display_name)`` pairs."""
    ordered = sorted(
        cameras,
        key=lambda item: (
            natural_key(sanitize_component(item[1], fallback="Camera")),
            item[0].casefold(),
            item[0],
        ),
    )
    used: set[str] = set()
    result: list[CameraSpec] = []
    for key, display_name in ordered:
        base = sanitize_component(display_name, fallback="Camera", max_length=64)
        candidate = base
        counter = 1
        while candidate.casefold() in used:
            counter += 1
            suffix = f"_{counter:02d}"
            candidate = f"{base[:64 - len(suffix)]}{suffix}"
        used.add(candidate.casefold())
        result.append(CameraSpec(key=key, display_name=display_name, output_name=candidate))
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
    digest = hashlib.blake2s(filename.encode("utf-8"), digest_size=8).hexdigest()
    if available <= len(suffix) + len(digest) + 1:
        raise ValueError("output directory leaves no safe filename budget")
    prefix = stem[: available - len(suffix) - len(digest) - 1].rstrip(" ._")
    return f"{prefix}_{digest}{suffix}"
