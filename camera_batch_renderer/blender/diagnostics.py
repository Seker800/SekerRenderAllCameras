from __future__ import annotations

import platform
import sys
import tempfile
from pathlib import Path

import bpy

from ..domain.naming import OUTPUT_DIRECTORY_NAME
from ..infrastructure.diagnostics import DiagnosticJournal
from ..version import VERSION_TEXT


def diagnostic_directories() -> list[Path]:
    directories = []
    if bpy.data.filepath:
        directories.append(Path(bpy.data.filepath).parent / OUTPUT_DIRECTORY_NAME / "Diagnostics")
    directories.append(Path(tempfile.gettempdir()) / "RenderAllCameras-Diagnostics")
    return directories


def find_diagnostics_directory(last_report: str = "") -> Path | None:
    """Find reports after a restart without persisting runtime properties in the blend."""
    candidates = ([Path(last_report).parent] if last_report else []) + diagnostic_directories()
    for directory in candidates:
        try:
            if directory.is_dir():
                return directory
        except OSError:
            continue
    return None


def begin_diagnostics(
    scene: bpy.types.Scene, channels: dict[str, bool]
) -> DiagnosticJournal | None:
    """Read host metadata without refreshing GPU devices or mutating preferences."""
    environment = {
        "blender": bpy.app.version_string,
        "blender_build": bpy.app.build_hash.decode("utf-8", errors="replace"),
        "addon": VERSION_TEXT,
        "python": sys.version,
        "os": platform.platform(),
        "blend_file": bpy.data.filepath,
        "scene": scene.name,
        "frame": scene.frame_current,
        "engine": scene.render.engine,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "resolution_percentage": scene.render.resolution_percentage,
        "format": scene.render.image_settings.file_format,
        "channels": channels,
        "render_display": bpy.context.preferences.view.render_display_type,
        "interface_locked": scene.render.use_lock_interface,
    }
    try:
        import gpu

        environment["display_gpu"] = {
            "vendor": gpu.platform.vendor_get(),
            "renderer": gpu.platform.renderer_get(),
            "driver": gpu.platform.version_get(),
        }
        if hasattr(gpu.platform, "backend_type_get"):
            environment["display_gpu"]["backend"] = gpu.platform.backend_type_get()
        if scene.render.engine == "CYCLES":
            environment["cycles"] = {
                "device": scene.cycles.device,
                "samples": scene.cycles.samples,
                "adaptive_sampling": scene.cycles.use_adaptive_sampling,
                "denoising": scene.cycles.use_denoising,
            }
            addon = bpy.context.preferences.addons.get("cycles")
            if addon is not None:
                preferences = addon.preferences
                environment["cycles"].update(
                    compute_device_type=preferences.compute_device_type,
                    cached_devices=[
                        {"name": d.name, "type": d.type, "enabled": d.use}
                        for d in preferences.devices
                    ],
                    devices_refreshed=False,
                )
    except Exception as exc:
        environment["device_info_error"] = str(exc)
    # Use a stable OS temp folder, not Blender's per-process temp folder (removed at exit).
    directories = diagnostic_directories()
    settings = getattr(scene, "rac_settings", None)
    if settings is not None:
        settings.diagnostic_path = ""
        settings.diagnostic_error = ""
    last_error = ""
    for directory in directories:
        journal = DiagnosticJournal(directory, environment)
        if journal.record("click_received", previous_write_error=last_error or None):
            if settings is not None:
                settings.diagnostic_path = str(journal.path)
            return journal
        last_error = journal.write_error
    if settings is not None:
        settings.diagnostic_error = f"Cannot write diagnostics: {last_error}"
    return None
