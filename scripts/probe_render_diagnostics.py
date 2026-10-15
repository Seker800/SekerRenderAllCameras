"""Real GUI reports for startup, rendering, cancellation and unwritable log destinations."""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from blender_test_safety import require_isolated_profile  # noqa: E402

require_isolated_profile()
sys.path.insert(0, os.environ.get("RAC_PACKAGE_PARENT", str(ROOT)))
import camera_batch_renderer  # noqa: E402
from camera_batch_renderer.blender.diagnostics import find_diagnostics_directory  # noqa: E402
from camera_batch_renderer.blender.render_adapter import BlenderRenderAdapter  # noqa: E402
from camera_batch_renderer.infrastructure.manifest import AtomicJsonWriter  # noqa: E402
from camera_batch_renderer.presentation import operators, runtime_state  # noqa: E402

directory = Path(os.environ["RAC_EXIT_OUTPUT"])
mode = os.environ["RAC_EXIT_MODE"]
bpy.ops.wm.read_factory_settings(use_empty=True)
camera_batch_renderer.register()
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 8192 if mode in {"heartbeat", "cancel"} else 16
scene.cycles.use_adaptive_sampling = False
scene.cycles.use_denoising = False
scene.render.resolution_x = scene.render.resolution_y = 256
scene.render.resolution_percentage = 100
scene.render.filepath = "unchanged-output"
bpy.ops.mesh.primitive_cube_add()
for index in range(2):
    camera = bpy.data.objects.new(f"Camera {index}", bpy.data.cameras.new(f"Camera {index}"))
    scene.collection.objects.link(camera)
    camera.location = (0, -7, 2)
    camera.rotation_euler = (-camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
fixture = directory / "diagnostics.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(fixture))
original_file = fixture.read_bytes()
original_camera = scene.camera
window = bpy.context.window_manager.windows[0]
started = False
cancel_requested = False
session = None
deadline = time.monotonic() + 150
original_create = operators.create_session
original_render = BlenderRenderAdapter.render_async
original_write = AtomicJsonWriter.write
fail_count = 0


def fail_start(*args, **kwargs):
    raise PermissionError("Injected startup permission failure")


def fail_render(adapter):
    global fail_count
    fail_count += 1
    if fail_count == 1:
        raise RuntimeError("Injected Cycles device failure")
    return original_render(adapter)


def fail_diagnostics(writer, payload):
    if writer.path.name.startswith("Render-"):
        if mode == "unwritable" or "Diagnostics" in writer.path.parts:
            raise PermissionError("Injected diagnostic destination failure")
    return original_write(writer, payload)


if mode == "startup":
    operators.create_session = fail_start
if mode == "render_failure":
    BlenderRenderAdapter.render_async = fail_render
if mode in {"fallback", "unwritable"}:
    AtomicJsonWriter.write = fail_diagnostics


def poll():
    global started, session, cancel_requested
    assert time.monotonic() < deadline, "Diagnostic probe stalled"
    if not started:
        area = next(a for a in window.screen.areas if a.type == "VIEW_3D")
        region = next(r for r in area.regions if r.type == "WINDOW")
        with bpy.context.temp_override(window=window, area=area, region=region):
            try:
                result = bpy.ops.render.render_all_cameras("INVOKE_DEFAULT")
                assert result == ({"CANCELLED"} if mode == "startup" else {"FINISHED"})
            except RuntimeError as exc:
                assert mode == "startup" and "Injected startup" in str(exc), exc
        session = runtime_state.active_session
        started = True
        return 0.05
    if mode == "cancel" and not cancel_requested and bpy.app.is_job_running("RENDER"):
        session.coordinator.request_cancel()
        cancel_requested = True
    if runtime_state.active_session is not None:
        return 0.05
    settings = scene.rac_settings
    if mode == "unwritable":
        assert not settings.diagnostic_path
        assert "Cannot write diagnostics" in settings.diagnostic_error
        assert session.coordinator.snapshot().status.value == "completed"
    else:
        report = Path(settings.diagnostic_path)
        data = json.loads(report.read_text(encoding="utf-8"))
        assert data["environment"]["cycles"]["device"] == "CPU"
        assert data["environment"]["channels"]["Beauty"] is True
        assert data["events"][0]["event"] == "click_received"
        if mode == "startup":
            assert data["last_checkpoint"]["event"] == "start_failed"
            assert "PermissionError" in data["errors"][0]["traceback"]
            assert session is None
        else:
            assert data["last_checkpoint"]["event"] == "finished"
            if mode == "render_failure":
                assert data["last_checkpoint"]["status"] == "failed"
                assert "Injected Cycles" in data["errors"][0]["error"]
                assert data["errors"][0]["action"]["camera"] == "Camera 0"
                assert "RuntimeError" in data["errors"][0]["traceback"]
            elif mode == "cancel":
                assert data["last_checkpoint"]["status"] == "cancelled"
                assert len(session.coordinator.snapshot().results) == 1
            else:
                assert data["last_checkpoint"]["status"] == "completed"
            if mode == "heartbeat":
                assert any(e["event"] == "rendering" for e in data["events"])
            if mode == "fallback":
                assert "RenderAllCameras-Diagnostics" in report.parts
                assert data["events"][0]["previous_write_error"]
        assert not list(report.parent.glob("*.tmp"))
        assert find_diagnostics_directory(str(report)) == report.parent
        # Runtime properties are SKIP_SAVE; reopening a file must still offer its report folder.
        assert find_diagnostics_directory() == report.parent
    assert scene.camera == original_camera
    assert scene.render.filepath == "unchanged-output"
    assert fixture.read_bytes() == original_file
    result = {"version": bpy.app.version_string, "mode": mode,
              "diagnostic_path": settings.diagnostic_path,
              "diagnostic_error": settings.diagnostic_error}
    (directory / "before-exit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("RENDER_DIAGNOSTICS_OK", json.dumps(result), flush=True)
    operators.create_session = original_create
    BlenderRenderAdapter.render_async = original_render
    AtomicJsonWriter.write = original_write
    camera_batch_renderer.unregister()
    for other in list(bpy.context.window_manager.windows):
        if other != window:
            with bpy.context.temp_override(window=other):
                bpy.ops.wm.window_close()
    bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=1.0)
    return None


def checked_poll():
    try:
        return poll()
    except Exception:
        error = traceback.format_exc()
        (directory / "failure.txt").write_text(error, encoding="utf-8")
        print(error, flush=True)
        bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=1.0)
        return None


bpy.app.timers.register(checked_poll, first_interval=0.5)
