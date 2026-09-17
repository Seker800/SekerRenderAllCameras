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

from camera_batch_renderer.blender.runtime import run_batch_sync  # noqa: E402
from camera_batch_renderer.blender.scene_reader import validate_scene  # noqa: E402
from camera_batch_renderer.infrastructure.storage import WORK_DIRECTORY_NAME  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_value_error(fragment: str, callback) -> None:
    try:
        callback()
    except ValueError as exc:
        assert_true(fragment in str(exc), f"Unexpected validation error: {exc}")
    else:
        raise AssertionError(f"Expected validation error containing: {fragment}")


def image_size(path: Path) -> tuple[int, int]:
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        return tuple(image.size[:2])
    finally:
        bpy.data.images.remove(image)


def image_mean_rgb(path: Path) -> tuple[float, float, float]:
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        pixels = image.pixels[:]
        count = max(1, len(pixels) // 4)
        return tuple(sum(pixels[channel::4]) / count for channel in range(3))
    finally:
        bpy.data.images.remove(image)


def image_red_range(path: Path) -> tuple[float, float]:
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        # Blender 4.0's bpy_prop_array does not support extended slices.
        values = tuple(image.pixels)[0::4]
        return min(values), max(values)
    finally:
        bpy.data.images.remove(image)


def add_camera(scene: bpy.types.Scene, name: str, *, orthographic: bool) -> bpy.types.Object:
    data = bpy.data.cameras.new(name)
    data.type = "ORTHO" if orthographic else "PERSP"
    if orthographic:
        data.ortho_scale = 5.0
    camera = bpy.data.objects.new(name, data)
    scene.collection.objects.link(camera)
    camera.location = (2.5 if orthographic else -2.5, -7.0, 2.5)
    camera.rotation_euler = (-camera.location).to_track_quat("-Z", "Y").to_euler()
    return camera


def assert_clean_output_directory(directory: Path) -> None:
    assert_true(
        not (directory / WORK_DIRECTORY_NAME).exists(),
        "Successful batch left its hidden working directory",
    )


def set_compositing(scene: bpy.types.Scene, enabled: bool) -> None:
    if hasattr(scene.render, "use_compositing"):
        scene.render.use_compositing = enabled
    else:
        scene.use_nodes = enabled


def compositor_tree(scene: bpy.types.Scene):
    set_compositing(scene, True)
    # Blender 4.x creates its compositor node tree by toggling Scene.use_nodes.
    # render.use_compositing only controls execution and can exist while node_tree is None.
    if hasattr(scene, "use_nodes"):
        scene.use_nodes = True
    if getattr(scene, "node_tree", None) is not None:
        return scene.node_tree
    tree = bpy.data.node_groups.new("Edge Case Compositor", "CompositorNodeTree")
    scene.compositing_node_group = tree
    return tree


def main() -> None:
    temporary = Path(tempfile.mkdtemp(prefix="rac-edge-cases-"))
    summary: dict[str, object] = {"blender": bpy.app.version_string}
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.render.resolution_x = 32
        scene.render.resolution_y = 32
        scene.render.resolution_percentage = 100

        expect_value_error(
            "Save the .blend file",
            lambda: validate_scene(
                scene,
                include_alpha=False,
                include_object_id=False,
                include_material_id=False,
            ),
        )

        fixture = temporary / "Edge 工况.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(fixture))
        expect_value_error(
            "no cameras",
            lambda: validate_scene(
                scene,
                include_alpha=False,
                include_object_id=False,
                include_material_id=False,
            ),
        )

        bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 0.0))
        cube = bpy.context.object
        cube.name = "Edge Cube"
        perspective = add_camera(scene, "Camera/A", orthographic=False)
        orthographic = add_camera(scene, "Camera?A", orthographic=True)
        orthographic.hide_render = True
        scene.camera = perspective
        original_camera = scene.camera
        original_filepath = "user/original/output"
        scene.render.filepath = original_filepath
        original_frame = 7
        scene.frame_set(original_frame)
        bpy.ops.wm.save_as_mainfile(filepath=str(fixture))
        fixture_bytes = fixture.read_bytes()

        scene.render.image_settings.file_format = "BMP"
        expect_value_error(
            "Unsupported output format",
            lambda: validate_scene(
                scene,
                include_alpha=False,
                include_object_id=False,
                include_material_id=False,
            ),
        )
        scene.render.image_settings.file_format = "PNG"
        scene.render.use_multiview = True
        expect_value_error(
            "Multi-view",
            lambda: validate_scene(
                scene,
                include_alpha=False,
                include_object_id=False,
                include_material_id=False,
            ),
        )
        scene.render.use_multiview = False

        format_extensions = {
            "PNG": ".png",
            "JPEG": ".jpg",
            "TIFF": ".tif",
            "OPEN_EXR": ".exr",
        }
        format_results: dict[str, list[str]] = {}
        for file_format, extension in format_extensions.items():
            scene.render.image_settings.file_format = file_format
            session = run_batch_sync(scene)
            progress = session.coordinator.snapshot()
            assert_true(progress.status.value == "completed", f"{file_format} failed")
            assert_true(len(progress.results) == 2, f"{file_format} missed a camera")
            assert_true(
                all(result.path.suffix.lower() == extension for result in progress.results),
                f"{file_format} used the wrong extension",
            )
            assert_true(
                len({result.path.name.casefold() for result in progress.results}) == 2,
                "Sanitized camera names collided",
            )
            assert_true(scene.camera == original_camera, "Active camera was not restored")
            assert_true(scene.render.filepath == original_filepath, "Output path was not restored")
            assert_true(scene.frame_current == original_frame, "Current frame was not restored")
            assert_clean_output_directory(session.allocation.directory)
            format_results[file_format] = [result.path.name for result in progress.results]
        summary["formats"] = format_results

        scene.render.image_settings.file_format = "PNG"
        for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            try:
                scene.render.engine = engine
                break
            except TypeError:
                continue
        tree = compositor_tree(scene)
        nodes = tree.nodes
        nodes.clear()
        file_output = nodes.new("CompositorNodeOutputFile")
        file_output_directory = temporary / "compositor-side-effects"
        file_output_directory.mkdir()
        if bpy.app.version >= (5, 0, 0):
            render_layers = nodes.new("CompositorNodeRLayers")
            output = nodes.new("NodeGroupOutput")
            tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
            output.inputs["Image"].default_value = (0.8, 0.05, 0.02, 1.0)
            tree.links.new(render_layers.outputs["Image"], file_output.inputs[0])
            file_output.directory = str(file_output_directory)
            file_output.file_name = "side_effect_"
        else:
            render_layers = nodes.new("CompositorNodeRLayers")
            rgb = nodes.new("CompositorNodeRGB")
            rgb.outputs[0].default_value = (0.8, 0.05, 0.02, 1.0)
            composite = nodes.new("CompositorNodeComposite")
            tree.links.new(rgb.outputs[0], composite.inputs[0])
            tree.links.new(render_layers.outputs["Image"], file_output.inputs[0])
            file_output.base_path = str(file_output_directory)
            file_output.file_slots[0].path = "side_effect_"
        node_signature = tuple(sorted(node.bl_idname for node in nodes))
        link_count = len(tree.links)
        compositor_session = run_batch_sync(scene, include_alpha=True)
        compositor_results = compositor_session.coordinator.snapshot().results
        assert_true(len(compositor_results) == 4, "Compositor batch missed an action")
        beauty_results = [
            result for result in compositor_results if result.channel.value == "Beauty"
        ]
        alpha_results = [result for result in compositor_results if result.channel.value == "Alpha"]
        for result in beauty_results:
            mean = image_mean_rgb(result.path)
            assert_true(mean[0] > mean[1] * 3.0, f"Final Composite was not used: {mean}")
        for result in alpha_results:
            minimum, maximum = image_red_range(result.path)
            assert_true(
                minimum < 0.05 and maximum > 0.95,
                f"Alpha auxiliary render did not bypass the Compositor: {(minimum, maximum)}",
            )
        assert_true(
            tuple(sorted(node.bl_idname for node in nodes)) == node_signature,
            "Compositor node tree changed",
        )
        assert_true(len(tree.links) == link_count, "Compositor links changed")
        assert_true(
            (file_output.directory if bpy.app.version >= (5, 0, 0) else file_output.base_path)
            == str(file_output_directory),
            "File Output path changed",
        )
        if bpy.app.version < (5, 0, 0):
            assert_true(
                any(file_output_directory.glob("side_effect_*")),
                "Existing File Output node did not execute",
            )
        summary["compositor"] = "Beauty composite, raw Alpha, and File Output node verified"

        set_compositing(scene, False)
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.render.use_border = True
        scene.render.use_crop_to_border = True
        scene.render.border_min_x = 0.25
        scene.render.border_max_x = 0.75
        scene.render.border_min_y = 0.25
        scene.render.border_max_y = 0.75
        cropped = run_batch_sync(
            scene,
            include_alpha=True,
            include_object_id=True,
            include_material_id=True,
        )
        cropped_results = cropped.coordinator.snapshot().results
        assert_true(len(cropped_results) == 8, "Cropped all-channel batch is incomplete")
        sizes = {result.channel.value: image_size(result.path) for result in cropped_results}
        assert_true(set(sizes.values()) == {(16, 16)}, f"Cropped channel sizes differ: {sizes}")
        assert_true(
            all(
                "_16x16_" in result.path.name or "_16x16." in result.path.name
                for result in cropped_results
            ),
            "Cropped output filenames do not report actual pixel dimensions",
        )
        assert_true(scene.render.use_border, "Render border setting changed")
        assert_true(scene.render.use_crop_to_border, "Crop-to-border setting changed")
        assert_clean_output_directory(cropped.allocation.directory)
        summary["render_border"] = sizes

        assert_true(
            fixture.read_bytes() == fixture_bytes,
            "The plug-in saved or changed the .blend",
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

        print("BLENDER_EDGE_CASES_OK", json.dumps(summary, ensure_ascii=False))
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


main()
