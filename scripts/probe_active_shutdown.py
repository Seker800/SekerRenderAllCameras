"""Disable the add-on while Cycles holds an auxiliary Scene; check deferred cleanup."""

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
from camera_batch_renderer.presentation.panel import RAC_PT_panel  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
camera_batch_renderer.register()
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 2048
scene.cycles.use_adaptive_sampling = False
scene.cycles.use_denoising = False
scene.render.resolution_x = scene.render.resolution_y = 256
scene.render.resolution_percentage = 100
scene.render.filepath = "original-output"
bpy.ops.mesh.primitive_cube_add()
for index in range(2):
    camera = bpy.data.objects.new(f"Shutdown {index}", bpy.data.cameras.new(f"Shutdown {index}"))
    scene.collection.objects.link(camera)
    camera.location = (0, -7, 2)
    camera.rotation_euler = (-camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
original_camera = scene.camera
scene.rac_settings.include_beauty = False
scene.rac_settings.include_alpha = True
directory = Path(os.environ["RAC_EXIT_OUTPUT"])
bpy.ops.wm.save_as_mainfile(filepath=str(directory / "shutdown.blend"))
fixture_bytes = (directory / "shutdown.blend").read_bytes()
started = False
shutdown_requested = False
auxiliary_name = None
deadline = time.monotonic() + 30


def poll():
    global started, shutdown_requested, auxiliary_name
    assert time.monotonic() < deadline, "Active disable did not finish"
    if not started:
        window = bpy.context.window_manager.windows[0]
        area = next(area for area in window.screen.areas if area.type == "VIEW_3D")
        region = next(region for region in area.regions if region.type == "WINDOW")
        with bpy.context.temp_override(window=window, area=area, region=region):
            assert bpy.ops.render.render_all_cameras("INVOKE_DEFAULT") == {"FINISHED"}
        started = True
        return 0.02
    session = runtime_state.active_session
    if not shutdown_requested:
        if not bpy.app.is_job_running("RENDER"):
            return 0.02
        assert session.adapter.auxiliary is not None
        auxiliary_name = session.adapter.auxiliary.scene.name
        camera_batch_renderer.unregister()
        assert runtime_state.active_session is session
        assert auxiliary_name in bpy.data.scenes, "Live auxiliary scene was deleted"
        assert hasattr(bpy.types.Scene, "rac_settings"), "UI removed while driver still owns it"
        assert session.coordinator.snapshot().cancel_requested
        shutdown_requested = True
        return 0.02
    if session is not None:
        return 0.02
    assert not bpy.app.is_job_running("RENDER")
    assert auxiliary_name not in bpy.data.scenes
    assert not hasattr(bpy.types.Scene, "rac_settings")
    assert not RAC_PT_panel.is_registered
    assert scene.camera == original_camera
    assert scene.render.filepath == "original-output"
    assert (directory / "shutdown.blend").read_bytes() == fixture_bytes
    info = json.loads(
        next((directory / "SekerRenderAllCameras").glob("*_RenderInfo.json")).read_text(
            encoding="utf-8"
        )
    )
    assert info["status"] == "cancelled" and len(info["results"]) == 1
    assert Path(info["results"][0]["path"]).is_file()
    result = {
        "version": bpy.app.version_string,
        "deferred_shutdown": True,
        "file_written": True,
        "result_count": len(info["results"]),
    }
    (directory / "before-exit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("ACTIVE_SHUTDOWN_OK", json.dumps(result), flush=True)
    for window in list(bpy.context.window_manager.windows)[1:]:
        with bpy.context.temp_override(window=window):
            bpy.ops.wm.window_close()
    bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=1.0)
    return None


bpy.app.timers.register(poll, first_interval=0.5)
