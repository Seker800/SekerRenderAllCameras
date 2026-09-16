from __future__ import annotations

import math
import uuid
from pathlib import Path

import bpy
import numpy as np
import OpenImageIO as oiio

from ..domain.palette import IdColor, allocate_colors

UNASSIGNED_MATERIAL_KEY = "builtin|<Unassigned>"


def _srgb_unit_to_linear(normalized: float) -> float:
    if normalized <= 0.04045:
        return normalized / 12.92
    return math.pow((normalized + 0.055) / 1.055, 2.4)


def _object_color_for_output(value: int) -> float:
    # Object.color is a gamma-color RNA property and Workbench applies the display transform.
    # Two inverse sRGB conversions produce the requested exact byte in the saved PNG.
    normalized = max(0.0, (value - 0.1) / 255.0)
    return _srgb_unit_to_linear(_srgb_unit_to_linear(normalized))


def _linear_to_byte(value: float) -> int:
    if value <= 0.0031308:
        srgb = value * 12.92
    else:
        srgb = 1.055 * math.pow(value, 1.0 / 2.4) - 0.055
    return round(max(0.0, min(1.0, srgb)) * 255)


def read_png_colors(path: Path) -> set[tuple[int, int, int]]:
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        pixels = list(image.pixels)
        return {
            tuple(_linear_to_byte(pixels[index + channel]) for channel in range(3))
            for index in range(0, len(pixels), 4)
        }
    finally:
        bpy.data.images.remove(image)


def save_render_alpha(output_path: Path, source: bpy.types.Image) -> None:
    width, height = source.size[:]
    pixels = np.asarray(source.pixels[:], dtype=np.float32).reshape((height, width, 4))
    alpha = np.rint(np.clip(pixels[:, :, 3], 0.0, 1.0) * 255.0).astype(np.uint8)
    # Blender exposes image rows bottom-to-top; image files use top-to-bottom scanlines.
    alpha = np.ascontiguousarray(np.flipud(alpha)[:, :, np.newaxis])
    image_output = oiio.ImageOutput.create(str(output_path))
    if image_output is None:
        raise RuntimeError(f"Cannot create Alpha image: {output_path}")
    specification = oiio.ImageSpec(width, height, 1, oiio.UINT8)
    try:
        if not image_output.open(str(output_path), specification):
            raise RuntimeError(image_output.geterror())
        if not image_output.write_image(alpha):
            raise RuntimeError(image_output.geterror())
    finally:
        image_output.close()


def save_file_alpha(source_path: Path, output_path: Path) -> None:
    source = bpy.data.images.load(str(source_path), check_existing=False)
    try:
        save_render_alpha(output_path, source)
    finally:
        bpy.data.images.remove(source)


def replace_with_file_alpha(output_path: Path) -> None:
    save_file_alpha(output_path, output_path)


def _configure_id_render(
    scene: bpy.types.Scene,
    source: bpy.types.Scene,
    output_path: Path,
    *,
    color_type: str,
) -> None:
    render = scene.render
    render.engine = "BLENDER_WORKBENCH"
    render.resolution_x = source.render.resolution_x
    render.resolution_y = source.render.resolution_y
    render.resolution_percentage = source.render.resolution_percentage
    render.pixel_aspect_x = source.render.pixel_aspect_x
    render.pixel_aspect_y = source.render.pixel_aspect_y
    render.image_settings.file_format = "PNG"
    render.image_settings.color_mode = "RGB"
    render.image_settings.color_depth = "8"
    render.filepath = str(output_path)
    render.film_transparent = False
    render.dither_intensity = 0.0
    scene.display.render_aa = "OFF"
    shading = scene.display.shading
    shading.light = "FLAT"
    shading.color_type = color_type
    shading.show_shadows = False
    shading.show_cavity = False
    shading.show_specular_highlight = False
    shading.background_type = "VIEWPORT"
    shading.background_color = (0.0, 0.0, 0.0)
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene.view_settings.use_curve_mapping = False


def _copy_camera(
    scene: bpy.types.Scene,
    camera: bpy.types.Object,
    objects: list[bpy.types.Object],
    data_blocks: list[bpy.types.ID],
) -> None:
    camera_data = camera.data.copy()
    camera_copy = bpy.data.objects.new(f"RAC_{camera.name}", camera_data)
    camera_copy.matrix_world = camera.matrix_world.copy()
    scene.collection.objects.link(camera_copy)
    scene.camera = camera_copy
    objects.append(camera_copy)
    data_blocks.append(camera_data)


def _object_key(obj: bpy.types.Object) -> str:
    library = obj.library.filepath if obj.library else "local"
    return f"{library}|{obj.name_full}|{obj.type}"


def _evaluated_candidates(
    depsgraph: bpy.types.Depsgraph,
    skipped: list[dict[str, str]],
) -> list[tuple[bpy.types.Object, object, str]]:
    candidates: list[tuple[bpy.types.Object, object, str]] = []
    for instance in depsgraph.object_instances:
        evaluated = instance.object
        original = evaluated.original
        if original.type in {"CAMERA", "LIGHT"} or original.hide_render:
            continue
        base_key = _object_key(original)
        if original.type == "VOLUME":
            skipped.append({"key": base_key, "reason": "Volume is not supported"})
            continue
        if instance.is_instance:
            owner = instance.parent.original if instance.parent else original
            persistent = ".".join(str(value) for value in instance.persistent_id)
            key = f"{base_key}|owner:{_object_key(owner)}|instance:{persistent}"
        else:
            key = base_key
        candidates.append((evaluated, instance.matrix_world.copy(), key))
    return candidates


def _cleanup_id_scene(
    scene: bpy.types.Scene,
    objects: list[bpy.types.Object],
    data_blocks: list[bpy.types.ID],
) -> None:
    if scene.name in bpy.data.scenes:
        bpy.data.scenes.remove(scene)
    for obj in reversed(objects):
        if obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj)
    for data in reversed(data_blocks):
        collection = getattr(bpy.data, f"{data.bl_rna.identifier.lower()}s", None)
        if collection is not None and data.name in collection:
            collection.remove(data)


class AlphaScene:
    def __init__(self, source: bpy.types.Scene, camera: bpy.types.Object, output_path: Path):
        self.scene = source.copy()
        self.scene.name = f"RAC_Alpha_{uuid.uuid4().hex}"
        self.scene.camera = camera
        self.scene.render.film_transparent = True
        self.scene.render.filepath = str(output_path)
        self.scene.render.image_settings.file_format = "PNG"
        self.scene.render.image_settings.color_mode = "RGBA"
        self.scene.render.image_settings.color_depth = "8"
        self.scene.use_nodes = False

    def cleanup(self) -> None:
        if self.scene.name in bpy.data.scenes:
            bpy.data.scenes.remove(self.scene)


class ObjectIdScene:
    def __init__(
        self,
        source: bpy.types.Scene,
        camera: bpy.types.Object,
        output_path: Path,
    ):
        self.scene = bpy.data.scenes.new(f"RAC_ObjectID_{uuid.uuid4().hex}")
        self._objects: list[bpy.types.Object] = []
        self._data: list[bpy.types.ID] = []
        self.skipped: list[dict[str, str]] = []
        self.colors: tuple[IdColor, ...] = ()
        self._configure(source, camera, output_path)

    @staticmethod
    def object_key(obj: bpy.types.Object) -> str:
        return _object_key(obj)

    def _configure(
        self, source: bpy.types.Scene, camera: bpy.types.Object, output_path: Path
    ) -> None:
        _configure_id_render(self.scene, source, output_path, color_type="OBJECT")
        _copy_camera(self.scene, camera, self._objects, self._data)

        depsgraph = bpy.context.evaluated_depsgraph_get()
        candidates = _evaluated_candidates(depsgraph, self.skipped)
        keys = [key for _evaluated, _matrix, key in candidates]
        self.colors = allocate_colors(keys)
        color_by_key = {item.key: item.rgb for item in self.colors}
        for evaluated, matrix_world, key in candidates:
            try:
                mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=depsgraph)
                duplicate = bpy.data.objects.new(f"RAC_{evaluated.name}", mesh)
                duplicate.matrix_world = matrix_world
                rgb = color_by_key[key]
                duplicate.color = tuple(_object_color_for_output(value) for value in rgb) + (1.0,)
                self.scene.collection.objects.link(duplicate)
                self._objects.append(duplicate)
                self._data.append(mesh)
            except Exception as exc:
                self.skipped.append({"key": key, "reason": str(exc)})

    def cleanup(self) -> None:
        _cleanup_id_scene(self.scene, self._objects, self._data)


class MaterialIdScene:
    def __init__(
        self,
        source: bpy.types.Scene,
        camera: bpy.types.Object,
        output_path: Path,
    ):
        self.scene = bpy.data.scenes.new(f"RAC_MaterialID_{uuid.uuid4().hex}")
        self._objects: list[bpy.types.Object] = []
        self._data: list[bpy.types.ID] = []
        self.skipped: list[dict[str, str]] = []
        self.colors: tuple[IdColor, ...] = ()
        self.material_names: dict[str, str] = {}
        self._configure(source, camera, output_path)

    @staticmethod
    def material_key(material: bpy.types.Material | None) -> str:
        if material is None:
            return UNASSIGNED_MATERIAL_KEY
        library = material.library.filepath if material.library else "local"
        return f"{library}|{material.name_full}"

    @staticmethod
    def material_name(material: bpy.types.Material | None) -> str:
        return material.name if material is not None else "Unassigned"

    def _configure(
        self, source: bpy.types.Scene, camera: bpy.types.Object, output_path: Path
    ) -> None:
        _configure_id_render(self.scene, source, output_path, color_type="MATERIAL")
        _copy_camera(self.scene, camera, self._objects, self._data)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        duplicates: list[tuple[bpy.types.Mesh, tuple[str, ...], tuple[int, ...]]] = []
        for evaluated, matrix_world, object_key in _evaluated_candidates(
            depsgraph, self.skipped
        ):
            try:
                mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=depsgraph)
                self._data.append(mesh)
                duplicate = bpy.data.objects.new(f"RAC_{evaluated.name}", mesh)
                self._objects.append(duplicate)
                duplicate.matrix_world = matrix_world
                self.scene.collection.objects.link(duplicate)
                materials = tuple(mesh.materials)
                if not materials:
                    materials = (None,)
                material_keys = tuple(self.material_key(material) for material in materials)
                material_indices = tuple(polygon.material_index for polygon in mesh.polygons)
                for material, key in zip(materials, material_keys, strict=True):
                    self.material_names[key] = self.material_name(material)
                duplicates.append((mesh, material_keys, material_indices))
            except Exception as exc:
                self.skipped.append({"key": object_key, "reason": str(exc)})

        self.colors = allocate_colors(self.material_names)
        material_by_key: dict[str, bpy.types.Material] = {}
        for color in self.colors:
            material = bpy.data.materials.new(f"RAC_MaterialID_{len(material_by_key):04d}")
            material.diffuse_color = tuple(
                _object_color_for_output(value) for value in color.rgb
            ) + (1.0,)
            material_by_key[color.key] = material
            self._data.append(material)

        for mesh, material_keys, material_indices in duplicates:
            mesh.materials.clear()
            for key in material_keys:
                mesh.materials.append(material_by_key[key])
            for polygon, material_index in zip(
                mesh.polygons, material_indices, strict=True
            ):
                polygon.material_index = material_index

    def cleanup(self) -> None:
        _cleanup_id_scene(self.scene, self._objects, self._data)
