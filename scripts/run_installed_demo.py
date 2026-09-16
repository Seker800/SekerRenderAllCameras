from __future__ import annotations

import importlib
import json
import os

import bpy


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    runtime = importlib.import_module("bl_ext.user_default.camera_batch_renderer.blender.runtime")
    auxiliary = importlib.import_module(
        "bl_ext.user_default.camera_batch_renderer.blender.auxiliary"
    )
    panel = importlib.import_module("bl_ext.user_default.camera_batch_renderer.presentation.panel")
    policy = importlib.import_module(
        "bl_ext.user_default.camera_batch_renderer.presentation.host_policy"
    )
    assert_true(
        policy.TARGET_ID == os.environ["RAC_EXPECTED_TARGET"],
        "Installed target policy does not match the selected Blender package",
    )
    assert_true(panel.RAC_PT_view3d_panel.is_registered, "Installed N-panel is not registered")
    assert_true(panel.RAC_PT_view3d_panel.bl_category == "Batch Render", "N-panel tab is wrong")
    scene = bpy.context.scene
    original_camera = scene.camera
    original_filepath = scene.render.filepath
    session = runtime.run_batch_sync(
        scene,
        include_alpha=True,
        include_object_id=True,
        include_material_id=True,
    )
    progress = session.coordinator.snapshot()
    assert_true(progress.status.value == "completed", "Installed batch did not complete")
    assert_true(len(progress.results) == 8, "Installed batch did not produce eight results")
    assert_true(all(result.path.exists() for result in progress.results), "An output is missing")
    assert_true(scene.camera == original_camera, "Active camera was not restored")
    assert_true(scene.render.filepath == original_filepath, "Render filepath was not restored")
    assert_true(
        not any(item.name.startswith("RAC_") for item in bpy.data.scenes),
        "Temporary scene leaked",
    )

    id_manifest = next(session.allocation.directory.glob("*_ObjectID.json"))
    id_payload = json.loads(id_manifest.read_text(encoding="utf-8"))
    allowed = {(0, 0, 0), *(tuple(item["rgb"]) for item in id_payload["objects"])}
    for result in progress.results:
        if result.channel.value == "ObjectID":
            colors = auxiliary.read_png_colors(result.path)
            assert_true(colors <= allowed, f"Object ID contains undeclared colors: {colors}")
            assert_true(colors - {(0, 0, 0)}, "Object ID contains no object label")
        elif result.channel.value == "Alpha" and result.camera_name == "Camera_01_Front":
            image = bpy.data.images.load(str(result.path), check_existing=False)
            try:
                width, height = image.size[:]
                pixels = list(image.pixels)
                bottom_center = pixels[(width // 2) * 4]
                top_center = pixels[((height - 1) * width + width // 2) * 4]
                assert_true(bottom_center > 0.95, "Alpha ground is not opaque")
                assert_true(top_center < 0.05, "Alpha world is not transparent")
            finally:
                bpy.data.images.remove(image)

    material_manifest = next(session.allocation.directory.glob("*_MaterialID.json"))
    material_payload = json.loads(material_manifest.read_text(encoding="utf-8"))
    material_allowed = {
        (0, 0, 0),
        *(tuple(item["rgb"]) for item in material_payload["materials"]),
    }
    for result in progress.results:
        if result.channel.value == "MaterialID":
            colors = auxiliary.read_png_colors(result.path)
            assert_true(
                colors <= material_allowed,
                f"Material ID contains undeclared colors: {colors}",
            )
            assert_true(colors - {(0, 0, 0)}, "Material ID contains no material label")

    render_info = next(session.allocation.directory.glob("*_RenderInfo.json"))
    payload = json.loads(render_info.read_text(encoding="utf-8"))
    assert_true(payload["status"] == "completed", "RenderInfo is not completed")
    assert_true(
        payload["blender_version"] == bpy.app.version_string,
        "RenderInfo Blender version does not match the running host",
    )
    print(
        "INSTALLED_DEMO_OK",
        json.dumps(
            {
                "directory": str(session.allocation.directory),
                "results": len(progress.results),
                "render_info": render_info.name,
                "object_id_info": id_manifest.name,
                "material_id_info": material_manifest.name,
            },
            ensure_ascii=False,
        ),
    )


main()
