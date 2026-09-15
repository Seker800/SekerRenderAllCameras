from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def look_at(camera: bpy.types.Object, target: tuple[float, float, float]) -> None:
    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def material(name: str, color: tuple[float, float, float, float], metallic: float = 0.0):
    result = bpy.data.materials.new(name)
    result.diffuse_color = color
    result.use_nodes = True
    principled = result.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = color
    metallic_input = (
        principled.inputs["Metallic IOR Level"]
        if "Metallic IOR Level" in principled.inputs
        else principled.inputs["Metallic"]
    )
    metallic_input.default_value = metallic
    principled.inputs["Roughness"].default_value = 0.32
    return result


def main(output_path: Path) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "Render All Cameras Demo"
    engine_items = scene.render.bl_rna.properties["engine"].enum_items.keys()
    scene.render.engine = (
        "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engine_items else "BLENDER_EEVEE"
    )
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.resolution_x = 256
    scene.render.resolution_y = 192
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.world = bpy.data.worlds.new("Demo World")
    scene.world.color = (0.025, 0.035, 0.065)

    bpy.ops.mesh.primitive_plane_add(size=14, location=(0.0, 0.0, 0.0))
    ground = bpy.context.object
    ground.name = "Ground"
    ground.data.materials.append(material("Ground Material", (0.09, 0.11, 0.16, 1.0)))

    bpy.ops.mesh.primitive_cube_add(size=2.4, location=(-1.35, 0.0, 1.2))
    cube = bpy.context.object
    cube.name = "Hero Cube"
    cube.rotation_euler.z = math.radians(18)
    cube.data.materials.append(material("Cube Material", (0.06, 0.32, 0.95, 1.0), 0.35))
    bevel = cube.modifiers.new("Soft Edges", "BEVEL")
    bevel.width = 0.16
    bevel.segments = 4

    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=(1.35, 0.25, 1.05))
    sphere = bpy.context.object
    sphere.name = "Hero Sphere"
    sphere.scale = (1.05, 1.05, 1.05)
    sphere.data.materials.append(material("Sphere Material", (0.95, 0.12, 0.055, 1.0), 0.05))
    bpy.ops.object.shade_smooth()

    bpy.ops.object.light_add(type="AREA", location=(0.0, -1.5, 6.5))
    key = bpy.context.object
    key.name = "Key Light"
    key.data.energy = 1150
    key.data.shape = "DISK"
    key.data.size = 5.0

    bpy.ops.object.light_add(type="AREA", location=(4.5, 2.0, 3.5))
    fill = bpy.context.object
    fill.name = "Fill Light"
    fill.data.energy = 650
    fill.data.color = (0.25, 0.45, 1.0)
    fill.data.size = 3.0
    look_at(fill, (0.0, 0.0, 1.0))

    cameras = (
        ("Camera_01_Front", (0.0, -9.5, 4.3), 52.0),
        ("Camera_02_Angle", (7.5, -7.0, 5.2), 58.0),
    )
    for name, location, lens in cameras:
        camera_data = bpy.data.cameras.new(name)
        camera_data.lens = lens
        camera = bpy.data.objects.new(name, camera_data)
        scene.collection.objects.link(camera)
        camera.location = location
        look_at(camera, (0.0, 0.0, 1.0))
    scene.camera = scene.objects["Camera_01_Front"]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    print(f"DEMO_SCENE_OK {output_path}")


if __name__ == "__main__":
    destination = Path(sys.argv[sys.argv.index("--") + 1])
    main(destination)
