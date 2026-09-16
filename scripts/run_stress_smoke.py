from __future__ import annotations

# ruff: noqa: I001

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import bpy


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PARENT = Path(os.environ.get("RAC_PACKAGE_PARENT", REPO_ROOT))
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from camera_batch_renderer.blender.runtime import run_batch_sync  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_no_temporary_data() -> None:
    for label, collection in (
        ("scenes", bpy.data.scenes),
        ("objects", bpy.data.objects),
        ("meshes", bpy.data.meshes),
        ("materials", bpy.data.materials),
        ("images", bpy.data.images),
    ):
        assert_true(
            not any(item.name.startswith("RAC_") for item in collection),
            f"Temporary data leaked in {label}",
        )


def main() -> None:
    temporary = Path(tempfile.mkdtemp(prefix="rac-stress-smoke-"))
    started = time.perf_counter()
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.render.image_settings.file_format = "PNG"
        scene.render.resolution_x = 8
        scene.render.resolution_y = 8
        scene.render.resolution_percentage = 100
        bpy.ops.mesh.primitive_cube_add(size=2.0)

        cameras = []
        for index in range(50):
            data = bpy.data.cameras.new(f"Stress Camera {index + 1:02d}")
            camera = bpy.data.objects.new(data.name, data)
            scene.collection.objects.link(camera)
            camera.location = (0.0, -8.0, 3.0)
            camera.rotation_euler = (1.2, 0.0, 0.0)
            cameras.append(camera)
        scene.camera = cameras[0]
        blend_path = temporary / "StressSmoke.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
        original_camera = scene.camera

        session = run_batch_sync(scene)
        progress = session.coordinator.snapshot()
        assert_true(progress.status.value == "completed", "50-camera batch failed")
        assert_true(len(progress.results) == 50, "50-camera batch lost results")
        assert_true(all(result.path.is_file() for result in progress.results), "Output missing")
        assert_true(scene.camera == original_camera, "50-camera batch did not restore camera")
        assert_no_temporary_data()

        for camera in cameras[3:]:
            data = camera.data
            bpy.data.objects.remove(camera, do_unlink=True)
            if data.users == 0:
                bpy.data.cameras.remove(data)
        scene.camera = cameras[0]
        expected_paths = None
        for iteration in range(10):
            repeated = run_batch_sync(scene)
            repeated_progress = repeated.coordinator.snapshot()
            assert_true(
                repeated_progress.status.value == "completed",
                f"Repeated batch {iteration + 1} failed",
            )
            assert_true(len(repeated_progress.results) == 3, "Repeated batch lost results")
            paths = tuple(sorted(str(result.path) for result in repeated_progress.results))
            if expected_paths is None:
                expected_paths = paths
            assert_true(paths == expected_paths, "Repeated batch output paths drifted")
            assert_no_temporary_data()

        print(
            "STRESS_SMOKE_OK",
            json.dumps(
                {
                    "blender": bpy.app.version_string,
                    "large_camera_count": 50,
                    "repeat_batches": 10,
                    "duration_seconds": round(time.perf_counter() - started, 3),
                },
                sort_keys=True,
            ),
        )
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


main()
