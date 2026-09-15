from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import bpy

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import camera_batch_renderer  # noqa: E402
from camera_batch_renderer.blender.runtime import run_batch_sync  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def linear_to_byte(value: float) -> int:
    if value <= 0.0031308:
        srgb = value * 12.92
    else:
        srgb = 1.055 * (value ** (1.0 / 2.4)) - 0.055
    return round(max(0.0, min(1.0, srgb)) * 255)


def image_rgb_values(path: Path) -> set[tuple[int, int, int]]:
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        pixels = list(image.pixels)
        return {
            tuple(linear_to_byte(pixels[index + channel]) for channel in range(3))
            for index in range(0, len(pixels), 4)
        }
    finally:
        bpy.data.images.remove(image)


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
        bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 0.0))
        cube = bpy.context.object
        cube.name = "Test Cube"
        original_cube_color = tuple(cube.color)
        camera_objects = []
        for index, name in enumerate(("Camera 10", "Camera 2")):
            camera_data = bpy.data.cameras.new(name)
            camera = bpy.data.objects.new(name, camera_data)
            scene.collection.objects.link(camera)
            camera.location = (index * 2.0, -7.0, 2.0)
            direction = -camera.location
            camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
            camera_objects.append(camera)
        scene.camera = camera_objects[0]
        original_camera = scene.camera
        original_filepath = scene.render.filepath
        fixture = temporary / "M2 Fixture.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(fixture))

        camera_batch_renderer.register()
        assert_true(hasattr(bpy.types.Scene, "rac_settings"), "Scene settings not registered")
        session = run_batch_sync(scene, include_alpha=True, include_object_id=True)
        progress = session.coordinator.snapshot()
        assert_true(progress.status.value == "completed", "Batch did not complete")
        assert_true(len(progress.results) == 6, "Expected six channel results")
        assert_true(all(result.path.exists() for result in progress.results), "Output missing")
        assert_true(progress.results[0].camera_name == "Camera 2", "Natural order is wrong")
        assert_true(scene.camera == original_camera, "Active camera was not restored")
        assert_true(scene.render.filepath == original_filepath, "Render filepath was not restored")
        assert_true(tuple(cube.color) == original_cube_color, "Original object color changed")
        assert_true(not session.allocation.marker.exists(), "Progress marker was not removed")
        assert_true((session.allocation.directory / "manifest.json").exists(), "Manifest missing")
        id_manifests = list(session.allocation.directory.glob("*_ObjectID.json"))
        assert_true(len(id_manifests) == 1, "Object ID manifest missing")
        id_payload = json.loads(id_manifests[0].read_text(encoding="utf-8"))
        allowed_colors = {(0, 0, 0), *(tuple(item["rgb"]) for item in id_payload["objects"])}
        id_results = [result for result in progress.results if result.channel.value == "ObjectID"]
        for result in id_results:
            actual_colors = image_rgb_values(result.path)
            assert_true(actual_colors <= allowed_colors, f"Unexpected ID colors: {actual_colors}")
            assert_true(actual_colors - {(0, 0, 0)}, "Object ID image contains no labels")
        alpha_results = [result for result in progress.results if result.channel.value == "Alpha"]
        for result in alpha_results:
            alpha_values = image_rgb_values(result.path)
            assert_true((0, 0, 0) in alpha_values, "Alpha has no transparent background")
            assert_true(
                (255, 255, 255) in alpha_values,
                f"Alpha has no opaque pixels: {alpha_values}",
            )

        scene.render.film_transparent = True
        transparent_session = run_batch_sync(scene, batch_start=2, include_alpha=True)
        transparent_progress = transparent_session.coordinator.snapshot()
        assert_true(len(transparent_progress.results) == 4, "Transparent Alpha reuse failed")
        assert_true(
            all(result.path.exists() for result in transparent_progress.results),
            "Transparent Alpha output missing",
        )
        assert_true(
            not any(item.name.startswith("RAC_") for item in bpy.data.scenes),
            "Temporary scene leaked",
        )
        camera_batch_renderer.unregister()
        assert_true(not hasattr(bpy.types.Scene, "rac_settings"), "Scene settings leaked")
        print("BLENDER_TESTS_OK")
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


main()
