from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import bpy

from ..domain import CameraEnvironmentSpec, Channel, RenderPlan, RenderSettings
from ..domain.naming import camera_specs
from .environment import collection_lights, id_key, scene_collection_path

SUPPORTED_FORMATS = {"PNG", "JPEG", "TIFF", "OPEN_EXR", "OPEN_EXR_MULTILAYER"}
AUXILIARY_ENGINES = {
    "BLENDER_EEVEE",
    "BLENDER_EEVEE_NEXT",
    "CYCLES",
    "BLENDER_WORKBENCH",
}


def camera_key(camera: bpy.types.Object) -> str:
    return id_key(camera)


def _environment_specs(
    scene: bpy.types.Scene,
    environment_pairs: tuple[
        tuple[bpy.types.Object | None, bpy.types.Collection | None, bpy.types.World | None], ...
    ],
) -> dict[str, CameraEnvironmentSpec]:
    scene_cameras = {id_key(obj): obj for obj in scene.objects if obj.type == "CAMERA"}
    light_objects = tuple(obj for obj in scene.objects if obj.type == "LIGHT")
    scene_lights = {id_key(obj) for obj in light_objects}
    result: dict[str, CameraEnvironmentSpec] = {}
    for camera, collection, world in environment_pairs:
        if camera is None:
            continue
        key = id_key(camera)
        if key not in scene_cameras:
            raise ValueError(f'Paired camera is not in the current scene: "{camera.name}"')
        if key in result:
            raise ValueError(f'Camera has more than one environment pairing: "{camera.name}"')
        if collection is None and world is None:
            continue
        light_keys = None
        collection_name = None
        if collection is not None:
            non_editable = next((obj for obj in light_objects if not obj.is_editable), None)
            if non_editable is not None:
                raise ValueError(
                    "Light isolation requires editable lights; create a library override for "
                    f'"{non_editable.name}"'
                )
            collection_key = id_key(collection)
            path = scene_collection_path(scene.collection, collection_key)
            if path is None:
                raise ValueError(
                    f'Paired light collection is not in the current scene: "{collection.name}"'
                )
            collection_name = collection.name
            light_keys = tuple(
                id_key(light)
                for light in collection_lights(collection)
                if id_key(light) in scene_lights
            )
        else:
            collection_key = None
        result[key] = CameraEnvironmentSpec(
            light_collection_name=collection_name,
            light_collection_key=collection_key,
            light_object_keys=light_keys,
            world_key=id_key(world) if world is not None else None,
            world_name=world.name if world is not None else None,
        )
    return result


def _samples(scene: bpy.types.Scene) -> int | None:
    if scene.render.engine == "CYCLES":
        return int(scene.cycles.samples)
    return None


def validate_scene(scene: bpy.types.Scene, *, include_alpha: bool, include_object_id: bool) -> None:
    if not bpy.data.filepath:
        raise ValueError("Save the .blend file before rendering")
    if scene.render.image_settings.file_format not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported output format: {scene.render.image_settings.file_format}")
    if scene.render.use_multiview:
        raise ValueError("Multi-view rendering is not supported")
    if not any(obj.type == "CAMERA" and obj.data is not None for obj in scene.objects):
        raise ValueError("The current scene has no cameras")
    if (include_alpha or include_object_id) and scene.render.engine not in AUXILIARY_ENGINES:
        raise ValueError("Alpha and Object ID are not validated for the current render engine")


def build_render_plan(
    scene: bpy.types.Scene,
    *,
    include_alpha: bool,
    include_object_id: bool,
    output_directory: Path,
    environment_pairs: tuple[
        tuple[bpy.types.Object | None, bpy.types.Collection | None, bpy.types.World | None], ...
    ] = (),
) -> RenderPlan:
    validate_scene(scene, include_alpha=include_alpha, include_object_id=include_object_id)
    environments = _environment_specs(scene, environment_pairs)
    cameras = camera_specs(
        (camera_key(obj), obj.name) for obj in scene.objects if obj.type == "CAMERA"
    )
    cameras = tuple(
        replace(camera, environment=environments.get(camera.key))
        for camera in cameras
    )
    scale = scene.render.resolution_percentage / 100.0
    channels = [Channel.BEAUTY]
    if include_alpha:
        channels.append(Channel.ALPHA)
    if include_object_id:
        channels.append(Channel.OBJECT_ID)
    blend_path = Path(bpy.data.filepath)
    engine = scene.render.engine
    engine_label = {
        "BLENDER_EEVEE": "EEVEE",
        "BLENDER_EEVEE_NEXT": "EEVEE",
        "CYCLES": "Cycles",
        "BLENDER_WORKBENCH": "Workbench",
    }.get(engine, engine)
    return RenderPlan(
        blend_path=blend_path,
        blend_name=blend_path.stem,
        output_directory=output_directory,
        scene_name=scene.name,
        view_layer_name=scene.view_layers[0].name,
        frame=scene.frame_current,
        cameras=cameras,
        channels=tuple(channels),
        settings=RenderSettings(
            engine=engine,
            engine_label=engine_label,
            width=max(1, round(scene.render.resolution_x * scale)),
            height=max(1, round(scene.render.resolution_y * scale)),
            file_format=scene.render.image_settings.file_format,
            file_extension=scene.render.file_extension,
            samples=_samples(scene),
            film_transparent=scene.render.film_transparent,
        ),
    )
