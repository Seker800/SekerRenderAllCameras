from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import bpy

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import camera_batch_renderer  # noqa: E402
from camera_batch_renderer.blender.runtime import run_beauty_batch_sync  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    temporary = Path(tempfile.mkdtemp(prefix="rac-blender-test-"))
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.render.image_settings.file_format = "PNG"
        scene.render.resolution_x = 32
        scene.render.resolution_y = 32
        scene.render.resolution_percentage = 100
        scene.render.filepath = "original-output"
        camera_objects = []
        for index, name in enumerate(("Camera 10", "Camera 2")):
            camera_data = bpy.data.cameras.new(name)
            camera = bpy.data.objects.new(name, camera_data)
            scene.collection.objects.link(camera)
            camera.location = (index * 2.0, -6.0, 2.0)
            camera.rotation_euler = (1.25, 0.0, 0.0)
            camera_objects.append(camera)
        scene.camera = camera_objects[0]
        original_camera = scene.camera
        original_filepath = scene.render.filepath
        fixture = temporary / "M2 Fixture.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(fixture))

        camera_batch_renderer.register()
        assert_true(hasattr(bpy.types.Scene, "rac_settings"), "Scene settings not registered")
        session = run_beauty_batch_sync(scene)
        progress = session.coordinator.snapshot()
        assert_true(progress.status.value == "completed", "Batch did not complete")
        assert_true(len(progress.results) == 2, "Expected two Beauty results")
        assert_true(all(result.path.exists() for result in progress.results), "Output missing")
        assert_true(progress.results[0].camera_name == "Camera 2", "Natural order is wrong")
        assert_true(scene.camera == original_camera, "Active camera was not restored")
        assert_true(scene.render.filepath == original_filepath, "Render filepath was not restored")
        assert_true(not session.allocation.marker.exists(), "Progress marker was not removed")
        assert_true((session.allocation.directory / "manifest.json").exists(), "Manifest missing")
        camera_batch_renderer.unregister()
        assert_true(not hasattr(bpy.types.Scene, "rac_settings"), "Scene settings leaked")
        print("BLENDER_TESTS_OK")
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


main()
