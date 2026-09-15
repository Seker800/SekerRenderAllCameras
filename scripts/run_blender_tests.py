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
from camera_batch_renderer.blender.runtime import create_session, run_batch_sync  # noqa: E402


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
        from camera_batch_renderer.presentation.panel import (  # noqa: PLC0415
            RAC_PT_panel,
            RAC_PT_view3d_panel,
        )

        assert_true(RAC_PT_panel.is_registered, "Output Properties panel not registered")
        assert_true(RAC_PT_view3d_panel.is_registered, "3D Viewport N-panel not registered")
        assert_true(RAC_PT_view3d_panel.bl_category == "Batch Render", "N-panel tab is wrong")
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
        assert_true(
            len(list(session.allocation.directory.glob("*_RenderInfo.json"))) == 1,
            "Manifest missing",
        )
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
                max(value[0] for value in alpha_values) >= 250,
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

        cancelled = create_session(
            scene, batch_start=3, include_alpha=False, include_object_id=False
        )
        cancelled.start()
        cancelled.prepare_current()
        cancelled.cancel()
        cancelled.finish()
        assert_true(
            cancelled.coordinator.snapshot().status.value == "cancelled",
            "Cancellation status is wrong",
        )
        assert_true(
            (cancelled.allocation.directory / ".incomplete").exists(),
            "Cancelled batch marker missing",
        )
        assert_true(scene.camera == original_camera, "Cancellation did not restore camera")

        from camera_batch_renderer.presentation import runtime_state  # noqa: PLC0415

        button_cancelled = create_session(
            scene, batch_start=5, include_alpha=False, include_object_id=False
        )
        button_cancelled.start()
        runtime_state.active_session = button_cancelled
        runtime_state.render_event = None
        assert_true(
            bpy.ops.render.cancel_all_cameras() == {"FINISHED"},
            "Cancel button failed",
        )
        assert_true(
            button_cancelled.coordinator.snapshot().cancel_requested,
            "Cancel button did not request cancellation",
        )
        assert_true(runtime_state.render_event == "cancelled", "Idle cancel event was not queued")
        button_cancelled.cancel()
        button_cancelled.finish()
        runtime_state.clear()

        failed = create_session(scene, batch_start=4, include_alpha=False, include_object_id=False)
        failed.start()
        failed.prepare_current()
        failed.fail("injected failure")
        failed.finish()
        failed_info = next(failed.allocation.directory.glob("*_RenderInfo.json"))
        failed_payload = json.loads(failed_info.read_text(encoding="utf-8"))
        assert_true(failed_payload["status"] == "failed", "Failure status is wrong")
        assert_true(scene.render.filepath == original_filepath, "Failure did not restore filepath")

        camera_batch_renderer.unregister()
        assert_true(not hasattr(bpy.types.Scene, "rac_settings"), "Scene settings leaked")
        from camera_batch_renderer.presentation.operators import (  # noqa: PLC0415
            _render_cancel,
            _render_complete,
        )

        assert_true(
            _render_complete not in bpy.app.handlers.render_complete,
            "Complete handler leaked",
        )
        assert_true(_render_cancel not in bpy.app.handlers.render_cancel, "Cancel handler leaked")
        print("BLENDER_TESTS_OK")
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


main()
