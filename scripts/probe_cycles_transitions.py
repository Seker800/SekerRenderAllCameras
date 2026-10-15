"""Isolated first-click and repeated Cycles/auxiliary-scene GUI transitions."""

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
from camera_batch_renderer.blender.render_adapter import BlenderRenderAdapter  # noqa: E402
from camera_batch_renderer.presentation import runtime_state  # noqa: E402

directory = Path(os.environ["RAC_EXIT_OUTPUT"])
mode = os.environ["RAC_EXIT_MODE"]
bpy.ops.wm.read_factory_settings(use_empty=True)
camera_batch_renderer.register()
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = int(os.environ.get("RAC_TEST_SAMPLES", "64"))
scene.cycles.use_adaptive_sampling = False
scene.cycles.use_denoising = False
scene.render.resolution_x = scene.render.resolution_y = 128
scene.render.resolution_percentage = 100
scene.render.filepath = "original-output"
scene.render.image_settings.file_format = "PNG"
bpy.ops.mesh.primitive_cube_add()
for index in range(2):
    camera = bpy.data.objects.new(f"Camera {index}", bpy.data.cameras.new(f"Camera {index}"))
    scene.collection.objects.link(camera)
    camera.location = (index, -7, 2)
    camera.rotation_euler = (-camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
for option in ("include_beauty", "include_alpha", "include_object_id", "include_material_id"):
    setattr(scene.rac_settings, option, True)
if mode == "single_layer":
    scene.render.use_single_layer = True
if mode == "locked":
    scene.render.use_lock_interface = True
fixture = directory / "transitions.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(fixture))
fixture_bytes = fixture.read_bytes()
if mode == "loaded":
    bpy.ops.wm.open_mainfile(filepath=str(fixture))
    scene = bpy.context.scene
original_camera = scene.camera
bpy.context.preferences.view.render_display_type = "WINDOW"
original_render = BlenderRenderAdapter.render_async


def traced_render(adapter):
    print("TRANSITION_START", adapter.render_scene.name, adapter.render_scene.render.filepath,
          "context", bpy.context.scene.name, flush=True)
    if os.environ.get("RAC_TRANSITION_VARIANT") == "native_display":
        preference = bpy.context.preferences.view.render_display_type
        try:
            bpy.context.preferences.view.render_display_type = "WINDOW"
            result = bpy.ops.render.render(
                "INVOKE_DEFAULT", write_still=True, scene=adapter.render_scene.name
            )
            assert result == {"RUNNING_MODAL"}, result
        finally:
            bpy.context.preferences.view.render_display_type = preference
    else:
        result = original_render(adapter)
    print("TRANSITION_ACCEPTED", sorted(result), flush=True)
    return result


BlenderRenderAdapter.render_async = traced_render
window = None
area = None
session = None
batch = 0
deadline = time.monotonic() + 180
observed_jobs = 0


def poll():
    global window, area, session, batch, observed_jobs
    assert time.monotonic() < deadline, "Cycles transition test stalled"
    if area is None:
        window = bpy.context.window_manager.windows[0]
        area = next(a for a in window.screen.areas if a.type == "VIEW_3D")
        with bpy.context.temp_override(window=window, area=area):
            if mode == "properties":
                area.type = "PROPERTIES"
            elif mode == "viewport":
                area.spaces.active.shading.type = "RENDERED"
            elif mode == "edit":
                bpy.context.view_layer.objects.active = next(o for o in scene.objects
                                                           if o.type == "MESH")
                bpy.ops.object.mode_set(mode="EDIT")
        return 0.5
    if session is None:
        region = next(r for r in area.regions if r.type == "WINDOW")
        with bpy.context.temp_override(window=window, area=area, region=region):
            assert bpy.ops.render.render_all_cameras("INVOKE_DEFAULT") == {"FINISHED"}
            session = runtime_state.active_session
            assert session is not None, "First click failed"
            assert not bpy.ops.render.render_all_cameras.poll()
        batch += 1
        print("BATCH_REQUEST", batch, flush=True)
        return 0.05
    if bpy.app.is_job_running("RENDER"):
        observed_jobs += 1
    if runtime_state.active_session is not None:
        return 0.05
    progress = session.coordinator.snapshot()
    assert progress.status.value == "completed", progress
    assert len(progress.results) == 8, progress
    assert all(r.path.is_file() and r.path.stat().st_size > 0 for r in progress.results)
    assert scene.camera == original_camera
    assert scene.render.filepath == "original-output"
    assert not any(s.name.startswith("RAC_") for s in bpy.data.scenes)
    assert fixture.read_bytes() == fixture_bytes
    assert bpy.context.preferences.view.render_display_type == "WINDOW"
    print("BATCH_VERIFIED", batch, flush=True)
    if batch < 3:
        session = None
        return 0.2
    result = {"version": bpy.app.version_string, "mode": mode, "batches": batch,
              "images": batch * 8, "observed_job_ticks": observed_jobs}
    (directory / "before-exit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("CYCLES_TRANSITIONS_OK", json.dumps(result), flush=True)
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
