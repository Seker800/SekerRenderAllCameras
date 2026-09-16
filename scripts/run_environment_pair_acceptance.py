from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Vector

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from camera_batch_renderer.blender.environment import id_key, layer_collections  # noqa: E402
from camera_batch_renderer.blender.runtime import run_batch_sync  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def point_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def make_world(name: str, color: tuple[float, float, float, float]) -> bpy.types.World:
    world = bpy.data.worlds.new(name)
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = color
    background.inputs["Strength"].default_value = 0.35
    return world


def make_light_rig(
    scene: bpy.types.Scene,
    name: str,
    color: tuple[float, float, float],
) -> tuple[bpy.types.Collection, bpy.types.Object]:
    collection = bpy.data.collections.new(name)
    child = bpy.data.collections.new(f"{name} Child")
    scene.collection.children.link(collection)
    collection.children.link(child)
    light_data = bpy.data.lights.new(f"{name} Area", type="AREA")
    light_data.energy = 900.0
    light_data.shape = "DISK"
    light_data.size = 4.0
    light_data.color = color
    light = bpy.data.objects.new(f"{name} Area", light_data)
    child.objects.link(light)
    light.location = (0.0, -2.5, 4.0)
    point_at(light, (0.0, 0.0, 0.5))
    return collection, light


def image_means(path: Path) -> tuple[float, float, float]:
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        pixels = image.pixels[:]
        count = max(1, len(pixels) // 4)
        return tuple(
            sum(pixels[channel::4]) / count
            for channel in range(3)
        )
    finally:
        bpy.data.images.remove(image)


def find_layer_collection(
    scene: bpy.types.Scene, collection: bpy.types.Collection
) -> bpy.types.LayerCollection:
    key = id_key(collection)
    return next(
        item
        for item in layer_collections(scene.view_layers[0])
        if id_key(item.collection) == key
    )


def main() -> None:
    acceptance_root = REPO_ROOT / "build" / "environment-pair-acceptance"
    if acceptance_root.exists():
        shutil.rmtree(acceptance_root)
    acceptance_root.mkdir(parents=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.resolution_x = 128
    scene.render.resolution_y = 128
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0

    neutral_world = make_world("Neutral World", (0.02, 0.02, 0.02, 1.0))
    red_world = make_world("Red World", (0.8, 0.01, 0.01, 1.0))
    blue_world = make_world("Blue World", (0.01, 0.01, 0.8, 1.0))
    scene.world = neutral_world

    bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 0.5))
    cube = bpy.context.object
    material = bpy.data.materials.new("White Test Material")
    material.diffuse_color = (0.8, 0.8, 0.8, 1.0)
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = (0.8, 0.8, 0.8, 1.0)
    principled.inputs["Roughness"].default_value = 0.7
    cube.data.materials.append(material)

    cameras: dict[str, bpy.types.Object] = {}
    for label in ("Red", "Blue"):
        camera_data = bpy.data.cameras.new(f"Camera {label}")
        camera = bpy.data.objects.new(f"Camera {label}", camera_data)
        scene.collection.objects.link(camera)
        camera.location = (0.0, -6.0, 2.2)
        point_at(camera, (0.0, 0.0, 0.5))
        cameras[label] = camera
    scene.camera = cameras["Red"]

    red_collection, red_light = make_light_rig(scene, "Red Rig", (1.0, 0.01, 0.01))
    blue_collection, blue_light = make_light_rig(scene, "Blue Rig", (0.01, 0.01, 1.0))
    red_layer = find_layer_collection(scene, red_collection)
    blue_layer = find_layer_collection(scene, blue_collection)

    red_collection.hide_render = True
    blue_collection.hide_render = True
    red_layer.exclude = True
    blue_layer.exclude = True
    red_light.hide_render = False
    blue_light.hide_render = True

    blend_path = acceptance_root / "Environment Pair Acceptance.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    original = {
        "camera": scene.camera,
        "world": scene.world,
        "red_collection": red_collection.hide_render,
        "blue_collection": blue_collection.hide_render,
        "red_layer": red_layer.exclude,
        "blue_layer": blue_layer.exclude,
        "red_light": red_light.hide_render,
        "blue_light": blue_light.hide_render,
    }

    session = run_batch_sync(
        scene,
        environment_pairs=(
            (cameras["Red"], red_collection, red_world),
            (cameras["Blue"], blue_collection, blue_world),
        ),
    )
    progress = session.coordinator.snapshot()
    assert_true(progress.status.value == "completed", "Environment batch did not complete")
    assert_true(len(progress.results) == 2, "Expected two Beauty outputs")
    assert_true(all(item.path.is_file() for item in progress.results), "Beauty output is missing")

    paths = {item.camera_name: item.path for item in progress.results}
    red_means = image_means(paths["Camera Red"])
    blue_means = image_means(paths["Camera Blue"])
    assert_true(red_means[0] > red_means[2] * 2.0, f"Red environment is wrong: {red_means}")
    assert_true(
        blue_means[2] > blue_means[0] * 2.0,
        f"Blue environment is wrong: {blue_means}",
    )
    assert_true(red_means[0] > blue_means[0] * 2.0, "Camera outputs used the same World")
    assert_true(blue_means[2] > red_means[2] * 2.0, "Camera outputs used the same light rig")

    manifest_path = next(session.allocation.directory.glob("*_RenderInfo.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert_true(manifest["status"] == "completed", "RenderInfo status is not completed")
    environments = {item["name"]: item["environment"] for item in manifest["cameras"]}
    assert_true(environments["Camera Red"]["world"] == "Red World", "Red World not recorded")
    assert_true(
        environments["Camera Blue"]["light_collection"] == "Blue Rig",
        "Blue light rig not recorded",
    )

    assert_true(scene.camera == original["camera"], "Active camera was not restored")
    assert_true(scene.world == original["world"], "World was not restored")
    assert_true(red_collection.hide_render == original["red_collection"], "Red rig changed")
    assert_true(blue_collection.hide_render == original["blue_collection"], "Blue rig changed")
    assert_true(red_layer.exclude == original["red_layer"], "Red layer exclusion changed")
    assert_true(blue_layer.exclude == original["blue_layer"], "Blue layer exclusion changed")
    assert_true(red_light.hide_render == original["red_light"], "Red light changed")
    assert_true(blue_light.hide_render == original["blue_light"], "Blue light changed")

    print(
        "ENVIRONMENT_PAIR_ACCEPTANCE_OK",
        json.dumps(
            {
                "blender": bpy.app.version_string,
                "blend": str(blend_path),
                "output_directory": str(session.allocation.directory),
                "red_image": str(paths["Camera Red"]),
                "blue_image": str(paths["Camera Blue"]),
                "red_mean_rgb": red_means,
                "blue_mean_rgb": blue_means,
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
        ),
    )


main()
