"""One request from each actual panel region, without a warm-up render or retry."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from blender_test_safety import require_isolated_profile  # noqa: E402

require_isolated_profile()
sys.path.insert(0, os.environ.get("RAC_PACKAGE_PARENT", str(ROOT)))
import camera_batch_renderer  # noqa: E402
from camera_batch_renderer.presentation import runtime_state  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
camera_batch_renderer.register()
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 16
scene.cycles.use_denoising = False
scene.render.resolution_x = scene.render.resolution_y = 64
scene.render.resolution_percentage = 100
bpy.ops.mesh.primitive_cube_add()
camera = bpy.data.objects.new("First Start", bpy.data.cameras.new("First Start"))
scene.collection.objects.link(camera)
camera.location = (0, -7, 2)
camera.rotation_euler = (-camera.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = camera
directory = Path(os.environ["RAC_EXIT_OUTPUT"])
bpy.ops.wm.save_as_mainfile(filepath=str(directory / "first-start.blend"))
mode = os.environ["RAC_EXIT_MODE"]
preference = mode.split("_")[-1]
bpy.context.preferences.view.render_display_type = preference
window = None
area = None
requested_at = None
job_started_at = None
request_count = 0
active_session = None
failed_start_checked = False


def poll():
    global requested_at, job_started_at, request_count, active_session, window, area
    global failed_start_checked
    if area is None:
        window = bpy.context.window_manager.windows[0]
        area = next(area for area in window.screen.areas if area.type == "VIEW_3D")
        with bpy.context.temp_override(window=window, area=area):
            if mode.startswith("PROPERTIES"):
                area.type = "PROPERTIES"
            else:
                area.spaces.active.show_region_ui = True
        return 0.3
    if requested_at is None:
        region_type = "WINDOW" if area.type == "PROPERTIES" else "UI"
        region = next(region for region in area.regions if region.type == region_type)
        with bpy.context.temp_override(window=window, area=area, region=region):
            if area.type == "PROPERTIES":
                area.spaces.active.context = "OUTPUT"
            if mode.startswith("FAIL") and not failed_start_checked:
                from camera_batch_renderer.blender.runtime import BlenderBatchSession

                original_start = BlenderBatchSession.start

                def fail_start(session):
                    session.coordinator.start()
                    raise OSError("Injected initial manifest failure")

                BlenderBatchSession.start = fail_start
                try:
                    try:
                        result = bpy.ops.render.render_all_cameras("INVOKE_DEFAULT")
                        assert result == {"CANCELLED"}
                    except RuntimeError as exc:
                        assert "Injected initial manifest failure" in str(exc)
                finally:
                    BlenderBatchSession.start = original_start
                assert runtime_state.active_session is None
                assert runtime_state.active_operator is None
                assert "Cannot start: Injected" in scene.rac_settings.status_text
                work = directory / "SekerRenderAllCameras/.render-all-cameras-work"
                assert (work / ".incomplete").is_file()
                assert not (work / "staging").exists()
                failed_start_checked = True
                return 0.1
            requested_at = time.monotonic()
            request_count += 1
            result = bpy.ops.render.render_all_cameras("INVOKE_DEFAULT")
            assert result == {"FINISHED"}, result
            active_session = runtime_state.active_session
            assert active_session is not None, "First request did not create a session"
            assert not bpy.ops.render.render_all_cameras.poll(), "Duplicate request is enabled"
        return 0.05
    if bpy.app.is_job_running("RENDER") and job_started_at is None:
        job_started_at = time.monotonic()
    if runtime_state.active_session is not None:
        assert time.monotonic() - requested_at < 20, "Single request stalled"
        return 0.05
    progress = active_session.coordinator.snapshot()
    assert progress.status.value == "completed", progress.error
    assert request_count == 1
    assert len(progress.results) == 1 and progress.results[0].path.is_file()
    assert bpy.context.preferences.view.render_display_type == preference
    result = {
        "version": bpy.app.version_string,
        "mode": mode,
        "requests": request_count,
        "failed_start_rolled_back": failed_start_checked,
        "file_written": True,
        "seconds": round(time.monotonic() - requested_at, 3),
        "launch_seconds": None
        if job_started_at is None
        else round(job_started_at - requested_at, 3),
    }
    (directory / "before-exit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("FIRST_START_OK", json.dumps(result), flush=True)
    camera_batch_renderer.unregister()
    for other in list(bpy.context.window_manager.windows):
        if other != window:
            with bpy.context.temp_override(window=other):
                bpy.ops.wm.window_close()
    bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=1.0)
    return None


bpy.app.timers.register(poll, first_interval=0.5)
