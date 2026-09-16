from __future__ import annotations

import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

import bpy

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import camera_batch_renderer  # noqa: E402

temporary = Path(tempfile.mkdtemp(prefix="rac-gui-host-control-"))
started = False
completed = False


def render_complete(*_args: object) -> None:
    global completed
    completed = True


def start_render() -> float | None:
    global started
    if started:
        if not completed:
            return 0.1
        output = temporary / "host-control.png"
        if not output.is_file():
            print("GUI_HOST_CONTROL_FAILED missing output", flush=True)
            os._exit(1)
        print("GUI_HOST_CONTROL_OK", flush=True)
        shutil.rmtree(temporary, ignore_errors=True)
        bpy.ops.wm.quit_blender()
        return None
    started = True
    try:
        scene = bpy.context.scene
        scene.render.filepath = str(temporary / "host-control.png")
        result = bpy.ops.render.render("INVOKE_DEFAULT", write_still=True, scene=scene.name)
        if result != {"RUNNING_MODAL"}:
            raise RuntimeError(f"Host render did not start: {result}")
        return 0.1
    except Exception:
        traceback.print_exc()
        print("GUI_HOST_CONTROL_FAILED", flush=True)
        os._exit(1)


bpy.ops.wm.read_factory_settings(use_empty=True)
camera_batch_renderer.register()
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.image_settings.file_format = "PNG"
scene.render.resolution_x = 32
scene.render.resolution_y = 32
scene.render.resolution_percentage = 100
bpy.ops.mesh.primitive_cube_add()
camera_data = bpy.data.cameras.new("Host Control Camera")
camera = bpy.data.objects.new("Host Control Camera", camera_data)
scene.collection.objects.link(camera)
camera.location = (0.0, -7.0, 2.0)
camera.rotation_euler = (-camera.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = camera
bpy.context.preferences.view.render_display_type = "NONE"
bpy.app.handlers.render_complete.append(render_complete)
bpy.app.timers.register(start_render, first_interval=2.0)
