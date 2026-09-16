from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import bpy

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PARENT = Path(os.environ.get("RAC_PACKAGE_PARENT", REPO_ROOT))
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

import camera_batch_renderer  # noqa: E402
from camera_batch_renderer.blender.environment import id_key, layer_collections  # noqa: E402
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
        material_a = bpy.data.materials.new("Test Material A")
        material_b = bpy.data.materials.new("Test Material B")
        material_a.diffuse_color = (0.8, 0.1, 0.1, 1.0)
        material_b.diffuse_color = (0.1, 0.1, 0.8, 1.0)
        cube.data.materials.append(material_a)
        cube.data.materials.append(material_b)
        for polygon in cube.data.polygons:
            polygon.material_index = 1 if polygon.normal.z > 0.5 else 0
        original_material_slots = tuple(cube.data.materials)
        original_material_colors = tuple(
            tuple(material.diffuse_color) for material in original_material_slots
        )
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
        light_collections = []
        light_objects = []
        worlds = []
        for index in range(2):
            parent = bpy.data.collections.new(f"Light Rig {index + 1}")
            child = bpy.data.collections.new(f"Light Rig {index + 1} Child")
            scene.collection.children.link(parent)
            parent.children.link(child)
            light_data = bpy.data.lights.new(f"Rig Light {index + 1}", type="POINT")
            light = bpy.data.objects.new(f"Rig Light {index + 1}", light_data)
            child.objects.link(light)
            light.hide_render = index == 1
            world = bpy.data.worlds.new(f"Camera World {index + 1}")
            light_collections.append(parent)
            light_objects.append(light)
            worlds.append(world)
        original_world = scene.world
        original_light_states = tuple(light.hide_render for light in light_objects)
        original_light_viewport_states = tuple(light.hide_viewport for light in light_objects)
        rig_two_layer = next(
            item
            for item in layer_collections(scene.view_layers[0])
            if id_key(item.collection) == id_key(light_collections[1])
        )
        light_collections[1].hide_render = True
        rig_two_layer.exclude = True
        environment_pairs = tuple(
            (camera_objects[index], light_collections[index], worlds[index])
            for index in range(2)
        )
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
        settings = scene.rac_settings
        assert_true(
            bpy.ops.render.camera_environment_pair_add() == {"FINISHED"},
            "Environment pair add operator failed",
        )
        settings.environment_pairs[0].camera = camera_objects[0]
        settings.environment_pairs[0].light_collection = light_collections[0]
        settings.environment_pairs[0].world = worlds[0]
        assert_true(scene.camera == camera_objects[0], "Pair edit did not preview its camera")
        assert_true(scene.world == worlds[0], "Pair edit did not preview its World")
        assert_true(not light_objects[0].hide_viewport, "Preview hid the paired light")
        assert_true(light_objects[1].hide_viewport, "Preview kept an unpaired light visible")
        assert_true(
            bpy.ops.render.camera_environment_pair_add() == {"FINISHED"},
            "Second environment pair add failed",
        )
        settings.environment_pairs[1].camera = camera_objects[1]
        settings.environment_pairs[1].light_collection = light_collections[1]
        settings.environment_pairs[1].world = worlds[1]
        assert_true(scene.camera == camera_objects[1], "Active pair did not switch the camera")
        assert_true(scene.world == worlds[1], "Active pair did not switch the World")
        assert_true(not rig_two_layer.exclude, "Preview did not reveal an excluded light rig")
        assert_true(
            not light_collections[1].hide_render,
            "Preview did not reveal a render-hidden light rig",
        )
        assert_true(light_objects[0].hide_viewport, "Preview kept the other rig visible")
        assert_true(not light_objects[1].hide_viewport, "Preview hid the selected rig")
        assert_true(
            light_collections[0].hide_render,
            "Preview did not disable the other paired collection",
        )
        assert_true(
            not light_objects[0].visible_get(view_layer=scene.view_layers[0]),
            "Preview eye visibility kept the other rig visible",
        )
        assert_true(
            light_objects[1].visible_get(view_layer=scene.view_layers[0]),
            "Preview eye visibility hid the selected rig",
        )
        settings.environment_pair_index = 0
        assert_true(scene.camera == camera_objects[0], "Pair row selection did not switch camera")
        assert_true(scene.world == worlds[0], "Pair row selection did not switch World")
        assert_true(
            not light_collections[0].hide_render,
            "Pair row selection did not enable its light collection",
        )
        assert_true(
            light_collections[1].hide_render and rig_two_layer.exclude,
            "Pair row selection did not disable the previous light collection",
        )
        assert_true(
            bpy.ops.render.camera_environment_pair_remove() == {"FINISHED"},
            "Environment pair remove operator failed",
        )
        assert_true(
            bpy.ops.render.camera_environment_pair_remove() == {"FINISHED"},
            "Second environment pair remove failed",
        )
        scene.camera = original_camera
        scene.world = original_world
        for light, hide_render, hide_viewport in zip(
            light_objects,
            original_light_states,
            original_light_viewport_states,
            strict=True,
        ):
            light.hide_render = hide_render
            light.hide_viewport = hide_viewport
        light_collections[1].hide_render = True
        rig_two_layer.exclude = True

        switching = create_session(
            scene,
            include_alpha=False,
            include_object_id=False,
            environment_pairs=(environment_pairs[1],),
        )
        switching.start()
        switching.prepare_current()
        assert_true(scene.world == worlds[1], "Camera 2 did not switch to its paired World")
        assert_true(light_objects[0].hide_render, "Unpaired light was not disabled")
        assert_true(not light_objects[1].hide_render, "Paired light was not enabled")
        assert_true(not rig_two_layer.exclude, "Render did not reveal the excluded light rig")
        assert_true(
            not light_collections[1].hide_render,
            "Render did not reveal the hidden light collection",
        )
        switching.adapter.render_sync()
        switching.complete_current()
        switching.prepare_current()
        assert_true(scene.world == original_world, "Unpaired camera did not restore scene World")
        assert_true(
            tuple(light.hide_render for light in light_objects) == original_light_states,
            "Unpaired camera did not restore the scene light setup",
        )
        assert_true(rig_two_layer.exclude, "Unpaired camera did not restore layer exclusion")
        assert_true(
            light_collections[1].hide_render,
            "Unpaired camera did not restore collection render visibility",
        )
        switching.cancel()
        switching.finish()
        assert_true(scene.world == original_world, "Cancelled pairing did not restore World")
        assert_true(
            tuple(light.hide_render for light in light_objects) == original_light_states,
            "Cancelled pairing did not restore light visibility",
        )
        assert_true(rig_two_layer.exclude, "Cancellation did not restore layer exclusion")
        assert_true(
            light_collections[1].hide_render,
            "Cancellation did not restore collection visibility",
        )

        session = run_batch_sync(
            scene,
            include_alpha=True,
            include_object_id=True,
            include_material_id=True,
            environment_pairs=environment_pairs,
        )
        progress = session.coordinator.snapshot()
        assert_true(progress.status.value == "completed", "Batch did not complete")
        assert_true(len(progress.results) == 8, "Expected eight channel results")
        assert_true(all(result.path.exists() for result in progress.results), "Output missing")
        assert_true(progress.results[0].camera_name == "Camera 2", "Natural order is wrong")
        assert_true(scene.camera == original_camera, "Active camera was not restored")
        assert_true(scene.render.filepath == original_filepath, "Render filepath was not restored")
        assert_true(scene.world == original_world, "World was not restored")
        assert_true(
            tuple(light.hide_render for light in light_objects) == original_light_states,
            "Light visibility was not restored",
        )
        assert_true(rig_two_layer.exclude, "Batch did not restore layer exclusion")
        assert_true(
            light_collections[1].hide_render,
            "Batch did not restore collection visibility",
        )
        assert_true(tuple(cube.color) == original_cube_color, "Original object color changed")
        assert_true(
            tuple(cube.data.materials) == original_material_slots,
            "Original material slots changed",
        )
        assert_true(
            tuple(tuple(material.diffuse_color) for material in original_material_slots)
            == original_material_colors,
            "Original material colors changed",
        )
        assert_true(not session.allocation.marker.exists(), "Progress marker was not removed")
        assert_true(
            len(list(session.allocation.directory.glob("*_RenderInfo.json"))) == 1,
            "Manifest missing",
        )
        render_info = next(session.allocation.directory.glob("*_RenderInfo.json"))
        render_payload = json.loads(render_info.read_text(encoding="utf-8"))
        environments = {
            item["name"]: item["environment"] for item in render_payload["cameras"]
        }
        assert_true(
            environments["Camera 2"] == {
                "light_collection": "Light Rig 2",
                "light_count": 1,
                "world": "Camera World 2",
            },
            "RenderInfo did not record the paired environment",
        )
        assert_true(
            session.allocation.directory == temporary / "SekerRenderAllCameras",
            "Output directory is not the fixed product folder",
        )
        assert_true(
            all(not result.path.name.startswith("001_") for result in progress.results),
            "A numeric batch prefix leaked into an output filename",
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
        material_manifests = list(session.allocation.directory.glob("*_MaterialID.json"))
        assert_true(len(material_manifests) == 1, "Material ID manifest missing")
        material_payload = json.loads(
            material_manifests[0].read_text(encoding="utf-8")
        )
        material_names = {item["name"] for item in material_payload["materials"]}
        assert_true(
            {"Test Material A", "Test Material B"} <= material_names,
            f"Material ID manifest is missing assigned materials: {material_names}",
        )
        allowed_material_colors = {
            (0, 0, 0),
            *(tuple(item["rgb"]) for item in material_payload["materials"]),
        }
        material_results = [
            result for result in progress.results if result.channel.value == "MaterialID"
        ]
        for result in material_results:
            actual_colors = image_rgb_values(result.path)
            assert_true(
                actual_colors <= allowed_material_colors,
                f"Unexpected Material ID colors: {actual_colors}",
            )
            assert_true(
                len(actual_colors - {(0, 0, 0)}) >= 2,
                f"Material ID image did not preserve face assignments: {actual_colors}",
            )
        alpha_results = [result for result in progress.results if result.channel.value == "Alpha"]
        for result in alpha_results:
            alpha_values = image_rgb_values(result.path)
            assert_true((0, 0, 0) in alpha_values, "Alpha has no transparent background")
            assert_true(
                max(value[0] for value in alpha_values) >= 250,
                f"Alpha has no opaque pixels: {alpha_values}",
            )

        scene.render.film_transparent = True
        disabled_channel_paths = {
            result.path
            for result in progress.results
            if result.channel.value in {"ObjectID", "MaterialID"}
        }
        overwritten_path = next(
            result.path for result in progress.results if result.channel.value == "Beauty"
        )
        overwritten_path.write_bytes(b"old output")
        stale_file = session.allocation.directory / "not-generated-this-run.png"
        stale_file.write_bytes(b"keep me")
        transparent_session = run_batch_sync(scene, include_alpha=True)
        transparent_progress = transparent_session.coordinator.snapshot()
        assert_true(len(transparent_progress.results) == 4, "Transparent Alpha reuse failed")
        assert_true(
            all(result.path.exists() for result in transparent_progress.results),
            "Transparent Alpha output missing",
        )
        assert_true(
            all(path.exists() for path in disabled_channel_paths),
            "Outputs for a disabled channel were removed",
        )
        assert_true(stale_file.read_bytes() == b"keep me", "Unrelated old output was changed")
        assert_true(
            overwritten_path.read_bytes().startswith(b"\x89PNG"),
            "A successful new render did not replace the same-name old output",
        )
        assert_true(
            {result.path for result in transparent_progress.results}
            == {
                result.path
                for result in progress.results
                if result.channel.value in {"Beauty", "Alpha"}
            },
            "A repeated render did not target the same output paths",
        )
        assert_true(
            not any(item.name.startswith("RAC_") for item in bpy.data.scenes),
            "Temporary scene leaked",
        )
        for collection, label in (
            (bpy.data.objects, "object"),
            (bpy.data.meshes, "mesh"),
            (bpy.data.materials, "material"),
        ):
            assert_true(
                not any(item.name.startswith("RAC_") for item in collection),
                f"Temporary {label} leaked",
            )

        cancelled = create_session(scene, include_alpha=False, include_object_id=False)
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
        assert_true(scene.world == original_world, "Cancellation did not restore World")
        assert_true(
            tuple(light.hide_render for light in light_objects) == original_light_states,
            "Cancellation did not restore light visibility",
        )

        material_cancelled = create_session(
            scene,
            include_alpha=False,
            include_object_id=False,
            include_material_id=True,
        )
        material_cancelled.start()
        material_cancelled.prepare_current()
        material_cancelled.adapter.render_sync()
        material_cancelled.complete_current()
        material_cancelled.prepare_current()
        assert_true(
            any(item.name.startswith("RAC_MaterialID_") for item in bpy.data.scenes),
            "Material ID cancellation fixture did not create an auxiliary scene",
        )
        material_cancelled.cancel()
        material_cancelled.finish()
        assert_true(
            not any(item.name.startswith("RAC_") for item in bpy.data.materials),
            "Material ID cancellation leaked temporary materials",
        )

        try:
            create_session(
                scene,
                include_alpha=False,
                include_object_id=False,
                environment_pairs=(environment_pairs[0], environment_pairs[0]),
            )
        except ValueError as exc:
            assert_true("more than one" in str(exc), "Duplicate pairing error is unclear")
        else:
            raise AssertionError("Duplicate camera pairing was accepted")

        from camera_batch_renderer.presentation import runtime_state  # noqa: PLC0415

        button_cancelled = create_session(scene, include_alpha=False, include_object_id=False)
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
        assert_true(
            runtime_state.render_event is None,
            "Cancel button must not impersonate a Blender render cancellation",
        )
        button_cancelled.cancel()
        button_cancelled.finish()
        runtime_state.clear()

        failed = create_session(
            scene,
            include_alpha=False,
            include_object_id=False,
            environment_pairs=environment_pairs,
        )
        failed.start()
        failed.prepare_current()
        assert_true(scene.world == worlds[1], "Failure fixture did not apply paired World")
        failed.fail("injected failure")
        failed.finish()
        failed_info = next(failed.allocation.directory.glob("*_RenderInfo.json"))
        failed_payload = json.loads(failed_info.read_text(encoding="utf-8"))
        assert_true(failed_payload["status"] == "failed", "Failure status is wrong")
        assert_true(failed_payload["schema_version"] == 2, "RenderInfo schema was not upgraded")
        assert_true("batch" not in failed_payload, "Removed batch field leaked into RenderInfo")
        assert_true(scene.render.filepath == original_filepath, "Failure did not restore filepath")
        assert_true(scene.world == original_world, "Failure did not restore World")
        assert_true(
            tuple(light.hide_render for light in light_objects) == original_light_states,
            "Failure did not restore light visibility",
        )
        assert_true(rig_two_layer.exclude, "Failure did not restore layer exclusion")
        assert_true(
            light_collections[1].hide_render,
            "Failure did not restore collection visibility",
        )
        assert_true(
            not any(
                path.name.startswith(".staging-")
                for path in session.allocation.directory.iterdir()
            ),
            "A render staging directory leaked",
        )

        material_failed = create_session(
            scene,
            include_alpha=False,
            include_object_id=False,
            include_material_id=True,
        )
        material_failed.start()
        material_failed.prepare_current()
        material_failed.adapter.render_sync()
        material_failed.complete_current()
        material_failed.prepare_current()
        material_failed.fail_current("injected material failure")
        material_failed.finish()
        assert_true(
            not any(item.name.startswith("RAC_") for item in bpy.data.materials),
            "Material ID failure leaked temporary materials",
        )
        assert_true(
            tuple(cube.data.materials) == original_material_slots,
            "Material ID failure changed original material slots",
        )

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
