from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Vector

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PARENT = Path(os.environ.get("RAC_PACKAGE_PARENT", REPO_ROOT))
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from camera_batch_renderer.blender.auxiliary import read_png_colors  # noqa: E402
from camera_batch_renderer.blender.runtime import run_batch_sync  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def point_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def main() -> None:
    acceptance_root = REPO_ROOT / "build" / "material-id-acceptance"
    if acceptance_root.exists():
        shutil.rmtree(acceptance_root)
    acceptance_root.mkdir(parents=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_x = 128
    scene.render.resolution_y = 128
    scene.render.resolution_percentage = 100

    bpy.ops.mesh.primitive_cube_add(location=(-0.8, 0.0, 0.0))
    assigned = next(obj for obj in scene.objects if obj.type == "MESH")
    assigned.name = "Two Material Cube"
    material_a = bpy.data.materials.new("Body Red")
    material_b = bpy.data.materials.new("Top Blue")
    material_a.diffuse_color = (0.8, 0.05, 0.05, 1.0)
    material_b.diffuse_color = (0.05, 0.05, 0.8, 1.0)
    assigned.data.materials.append(material_a)
    assigned.data.materials.append(material_b)
    for polygon in assigned.data.polygons:
        polygon.material_index = 1 if polygon.normal.z > 0.5 else 0

    bpy.ops.mesh.primitive_cube_add(location=(1.1, 0.0, -0.25), scale=(0.55, 0.55, 0.75))
    unassigned = next(
        obj for obj in scene.objects if obj.type == "MESH" and obj != assigned
    )
    unassigned.name = "Unassigned Cube"

    camera_data = bpy.data.cameras.new("Material Camera")
    camera = bpy.data.objects.new("Material Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (4.2, -8.0, 4.8)
    point_at(camera, (0.0, 0.0, 0.0))
    camera.data.lens = 52
    scene.camera = camera

    original_slots = tuple(assigned.data.materials)
    original_indices = tuple(polygon.material_index for polygon in assigned.data.polygons)
    original_colors = tuple(tuple(material.diffuse_color) for material in original_slots)
    fixture = acceptance_root / "Material ID Acceptance.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(fixture))

    session = run_batch_sync(scene, include_material_id=True)
    progress = session.coordinator.snapshot()
    assert_true(progress.status.value == "completed", "Material ID batch did not complete")
    assert_true(len(progress.results) == 2, "Expected Beauty and Material ID outputs")
    material_result = next(
        result for result in progress.results if result.channel.value == "MaterialID"
    )
    manifest_path = acceptance_root / "SekerRenderAllCameras" / (
        "Material ID Acceptance_MaterialID.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mapping = {item["name"]: tuple(item["rgb"]) for item in manifest["materials"]}
    assert_true(
        {"Body Red", "Top Blue", "Unassigned"} <= mapping.keys(),
        f"Material mapping is incomplete: {sorted(mapping)}",
    )
    actual_colors = read_png_colors(material_result.path)
    expected_labels = {mapping["Body Red"], mapping["Top Blue"], mapping["Unassigned"]}
    assert_true((0, 0, 0) in actual_colors, "Material ID background is not black")
    assert_true(
        expected_labels <= actual_colors,
        f"Material ID pixels are missing labels: expected {expected_labels}, got {actual_colors}",
    )
    assert_true(
        tuple(assigned.data.materials) == original_slots,
        "Material ID changed the user's material slots",
    )
    assert_true(
        tuple(polygon.material_index for polygon in assigned.data.polygons) == original_indices,
        "Material ID changed the user's face assignments",
    )
    assert_true(
        tuple(tuple(material.diffuse_color) for material in original_slots) == original_colors,
        "Material ID changed the user's material colors",
    )
    for collection, label in (
        (bpy.data.scenes, "scene"),
        (bpy.data.objects, "object"),
        (bpy.data.meshes, "mesh"),
        (bpy.data.materials, "material"),
    ):
        assert_true(
            not any(item.name.startswith("RAC_") for item in collection),
            f"Temporary {label} leaked",
        )

    summary = {
        "blender": bpy.app.version_string,
        "blend": str(fixture),
        "material_image": str(material_result.path),
        "material_manifest": str(manifest_path),
        "pixel_colors": sorted(actual_colors),
        "mapping": mapping,
    }
    print("MATERIAL_ID_ACCEPTANCE_OK", json.dumps(summary, ensure_ascii=False))


main()
