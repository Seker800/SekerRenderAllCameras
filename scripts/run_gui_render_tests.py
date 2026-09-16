from __future__ import annotations

import atexit
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

import bpy

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import camera_batch_renderer  # noqa: E402
from camera_batch_renderer.presentation import runtime_state  # noqa: E402

temporary = Path(tempfile.mkdtemp(prefix="rac-gui-test-"))
atexit.register(shutil.rmtree, temporary, True)
started_at = time.monotonic()
phase = "start_success"
max_window_count = 0
original_camera = None
original_filepath = ""
original_world = None
environment_lights = []
original_light_states = ()


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def invoke_from_view3d(operator) -> set[str]:
    window = bpy.context.window_manager.windows[0]
    area = next(item for item in window.screen.areas if item.type == "VIEW_3D")
    region = next(item for item in area.regions if item.type == "WINDOW")
    with bpy.context.temp_override(window=window, area=area, region=region):
        return operator("INVOKE_DEFAULT")


def prepare_scene() -> None:
    global original_camera, original_filepath, original_world, original_light_states
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_x = 32
    scene.render.resolution_y = 32
    scene.render.resolution_percentage = 100
    scene.render.filepath = "original-output"
    bpy.ops.mesh.primitive_cube_add()
    cube = next(obj for obj in scene.objects if obj.type == "MESH")
    material = bpy.data.materials.new("GUI Test Material")
    cube.data.materials.append(material)
    for index in range(3):
        camera_data = bpy.data.cameras.new(f"Camera {index + 1}")
        camera = bpy.data.objects.new(f"Camera {index + 1}", camera_data)
        scene.collection.objects.link(camera)
        camera.location = (index * 2.0, -7.0, 2.0)
        camera.rotation_euler = (-camera.location).to_track_quat("-Z", "Y").to_euler()
        if index == 0:
            scene.camera = camera
    original_camera = scene.camera
    original_filepath = scene.render.filepath
    original_world = scene.world
    light_collection = bpy.data.collections.new("GUI Camera Light Rig")
    scene.collection.children.link(light_collection)
    for index in range(2):
        light_data = bpy.data.lights.new(f"GUI Light {index + 1}", type="POINT")
        light = bpy.data.objects.new(f"GUI Light {index + 1}", light_data)
        if index:
            scene.collection.objects.link(light)
        else:
            light_collection.objects.link(light)
        light.hide_render = index == 1
        environment_lights.append(light)
    original_light_states = tuple(light.hide_render for light in environment_lights)
    paired_world = bpy.data.worlds.new("GUI Camera World")
    bpy.ops.wm.save_as_mainfile(filepath=str(temporary / "GUI Fixture.blend"))
    camera_batch_renderer.register()
    scene.rac_settings.include_material_id = True
    pair = scene.rac_settings.environment_pairs.add()
    pair.camera = scene.camera
    pair.light_collection = light_collection
    pair.world = paired_world
    original_world = scene.world
    original_light_states = tuple(light.hide_render for light in environment_lights)
    bpy.context.preferences.view.render_display_type = "WINDOW"


def validate_result() -> None:
    scene = bpy.context.scene
    output = temporary / "SekerRenderAllCameras"
    images = list(output.glob("*_Beauty_*.png"))
    material_images = list(output.glob("*_MaterialID_*.png"))
    manifests = list(output.glob("*_RenderInfo.json"))
    assert_true(len(images) == 3, f"Expected three GUI renders, found {len(images)}")
    assert_true(
        len(material_images) == 3,
        f"Expected three GUI Material ID renders, found {len(material_images)}",
    )
    assert_true((output / "GUI Fixture_MaterialID.json").is_file(), "Material ID JSON missing")
    assert_true(len(manifests) == 1, "GUI RenderInfo is missing")
    payload = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert_true(payload["status"] == "completed", "GUI batch did not complete")
    assert_true(len(payload["results"]) == 6, "GUI results were not fully recorded")
    assert_true(scene.camera == original_camera, "GUI test did not restore active camera")
    assert_true(scene.render.filepath == original_filepath, "GUI test did not restore filepath")
    assert_true(scene.world == original_world, "GUI test did not restore World")
    assert_true(
        tuple(light.hide_render for light in environment_lights) == original_light_states,
        "GUI test did not restore light visibility",
    )
    assert_true(
        bpy.context.preferences.view.render_display_type == "WINDOW",
        "GUI test changed the render display preference",
    )
    assert_true(not runtime_state.active_session, "GUI runtime session leaked")
    assert_true(
        not any(path.name.startswith(".staging-") for path in output.iterdir()),
        "GUI render staging directory leaked",
    )
    assert_true(
        not any(item.name.startswith("RAC_") for item in bpy.data.materials),
        "GUI Material ID render leaked temporary materials",
    )
    assert_true(max_window_count == 1, "GUI batch opened a separate render window")


def start_cancel_test() -> None:
    result = invoke_from_view3d(bpy.ops.render.render_all_cameras)
    assert_true(result == {"RUNNING_MODAL"}, f"Cancel batch did not start: {result}")
    assert_true(
        invoke_from_view3d(bpy.ops.render.cancel_all_cameras) == {"FINISHED"},
        "Cancel request was rejected",
    )
    assert_true(runtime_state.render_event is None, "Cancel request forged a render event")


def validate_cancel_result() -> None:
    output = temporary / "SekerRenderAllCameras"
    images = list(output.glob("*_Beauty_*.png"))
    manifest = next(output.glob("*_RenderInfo.json"))
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert_true(payload["status"] == "cancelled", "GUI cancel status is wrong")
    assert_true(len(payload["results"]) == 1, "GUI cancel did not finish the current image")
    assert_true(len(images) == 3, "GUI cancel removed old images that were not regenerated")
    assert_true((output / ".incomplete").is_file(), "GUI cancel marker is missing")
    assert_true(bpy.context.scene.world == original_world, "GUI cancel did not restore World")
    assert_true(
        tuple(light.hide_render for light in environment_lights) == original_light_states,
        "GUI cancel did not restore light visibility",
    )
    assert_true(
        bpy.context.preferences.view.render_display_type == "WINDOW",
        "GUI cancel changed the render display preference",
    )


def poll() -> float | None:
    global max_window_count, phase
    try:
        elapsed = time.monotonic() - started_at
        max_window_count = max(max_window_count, len(bpy.context.window_manager.windows))
        if phase == "start_success":
            result = invoke_from_view3d(bpy.ops.render.render_all_cameras)
            assert_true(result == {"RUNNING_MODAL"}, f"GUI batch did not start: {result}")
            assert_true(
                bpy.context.preferences.view.render_display_type == "WINDOW",
                "GUI batch changed the render display preference",
            )
            phase = "success"
            return 0.1
        if phase == "success" and runtime_state.active_session is None:
            validate_result()
            start_cancel_test()
            phase = "cancel"
            return 0.1
        if phase == "cancel" and runtime_state.active_session is None:
            validate_cancel_result()
            camera_batch_renderer.unregister()
            print("GUI_RENDER_TESTS_OK", flush=True)
            bpy.ops.wm.quit_blender()
            return None
        if elapsed > 20.0:
            raise TimeoutError("GUI batch stalled after a missed render_complete event")
        return 0.1
    except Exception:
        traceback.print_exc()
        print("GUI_RENDER_TESTS_FAILED", flush=True)
        shutil.rmtree(temporary, ignore_errors=True)
        os._exit(1)


prepare_scene()
bpy.app.timers.register(poll, first_interval=0.25)
