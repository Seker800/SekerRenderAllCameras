"""Small isolated native render used to bisect imports/registration/exit crashes."""

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
sys.path.insert(0, str(ROOT))
mode = os.environ.get("RAC_EXIT_MODE", "native")
if mode == "numpy":
    import numpy  # noqa: F401
elif mode == "oiio":
    import OpenImageIO  # noqa: F401
elif mode == "adapter":
    import camera_batch_renderer.blender  # noqa: F401
elif mode in {"registered", "unregistered"}:
    import camera_batch_renderer

if os.environ.get("RAC_EXIT_FACTORY_RESET", "1") == "1":
    bpy.ops.wm.read_factory_settings(use_empty=True)
else:
    for obj in list(bpy.context.scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
if mode in {"registered", "unregistered"}:
    camera_batch_renderer.register()

scene = bpy.context.scene
scene.render.engine = os.environ.get("RAC_EXIT_ENGINE", "BLENDER_WORKBENCH")
scene.render.resolution_x = scene.render.resolution_y = 64
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
if scene.render.engine == "CYCLES":
    scene.cycles.device = "CPU"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = False
    if mode in {"native_window", "native_sequence"}:
        scene.render.resolution_x = scene.render.resolution_y = 512
        scene.cycles.samples = 1024
        scene.cycles.use_adaptive_sampling = False
bpy.ops.mesh.primitive_cube_add()
camera = bpy.data.objects.new("Probe Camera", bpy.data.cameras.new("Probe Camera"))
scene.collection.objects.link(camera)
camera.location = (0, -7, 2)
camera.rotation_euler = (-camera.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = camera
bpy.context.preferences.view.render_display_type = "NONE"
output = Path(os.environ["RAC_EXIT_OUTPUT"])
scene.render.filepath = str(output / "probe.png")
started = False
completed = False
window_ready = False
second_scene = None
scene_window = bpy.context.window_manager.windows[0]
deadline = time.monotonic() + 120


def on_complete(*_args):
    global completed
    completed = True


def poll():
    global started, window_ready, second_scene, completed
    if time.monotonic() > deadline:
        raise TimeoutError("Native render probe stalled")
    if not started:
        if mode in {"native_window", "native_sequence"} and not window_ready:
            with bpy.context.temp_override(window=scene_window):
                bpy.context.preferences.view.render_display_type = "WINDOW"
                bpy.ops.render.view_show("INVOKE_DEFAULT")
                bpy.context.preferences.view.render_display_type = "NONE"
            window_ready = True
            return 0.3
        started = True
        with bpy.context.temp_override(window=scene_window):
            assert bpy.ops.render.render("INVOKE_DEFAULT", write_still=True) == {"RUNNING_MODAL"}
        return 0.1
    if not completed or bpy.app.is_job_running("RENDER"):
        return 0.1
    assert (output / "probe.png").is_file()
    if mode == "native_sequence" and second_scene is None:
        second_scene = scene.copy()
        second_scene.name = "Native Alpha Scene"
        second_scene.render.film_transparent = True
        second_scene.render.filepath = str(output / "alpha.png")
        second_scene.render.image_settings.color_mode = "RGBA"
        completed = False
        with bpy.context.temp_override(window=scene_window):
            assert bpy.ops.render.render(
                "INVOKE_DEFAULT", write_still=True, scene=second_scene.name
            ) == {"RUNNING_MODAL"}
        return 0.1
    if second_scene is not None:
        assert (output / "alpha.png").is_file()
        for window in bpy.context.window_manager.windows:
            if window.scene == second_scene:
                window.scene = scene
        bpy.data.scenes.remove(second_scene)
    bpy.app.handlers.render_complete.remove(on_complete)
    if mode == "unregistered":
        camera_batch_renderer.unregister()
    result = {
        "version": bpy.app.version_string,
        "mode": mode,
        "engine": scene.render.engine,
        "file_written": True,
        "job_idle": True,
        "numpy_imported": "numpy" in sys.modules,
        "oiio_imported": "OpenImageIO" in sys.modules,
        "addon_imported": "camera_batch_renderer" in sys.modules,
    }
    (output / "before-exit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("EXIT_PROBE_RENDER_OK", json.dumps(result), flush=True)
    bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=1.0)
    return None


bpy.app.handlers.render_complete.append(on_complete)
bpy.app.timers.register(poll, first_interval=0.5)
