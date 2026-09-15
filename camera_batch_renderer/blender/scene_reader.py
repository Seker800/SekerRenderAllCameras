from __future__ import annotations

from pathlib import Path

import bpy

from camera_batch_renderer.domain import Channel, ConflictPolicy, RenderPlan, RenderSettings
from camera_batch_renderer.domain.naming import camera_specs, format_batch

SUPPORTED_FORMATS = {"PNG", "JPEG", "TIFF", "OPEN_EXR", "OPEN_EXR_MULTILAYER"}


def camera_key(camera: bpy.types.Object) -> str:
    library = camera.library.filepath if camera.library else "local"
    return f"{library}|{camera.name_full}"


def _samples(scene: bpy.types.Scene) -> int | None:
    if scene.render.engine == "CYCLES":
        return int(scene.cycles.samples)
    return None


def build_render_plan(
    scene: bpy.types.Scene,
    *,
    batch_number: int,
    include_alpha: bool,
    include_object_id: bool,
    output_directory: Path,
) -> RenderPlan:
    if not bpy.data.filepath:
        raise ValueError("Save the .blend file before rendering")
    if scene.render.image_settings.file_format not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported output format: {scene.render.image_settings.file_format}")
    if scene.render.use_multiview:
        raise ValueError("Multi-view rendering is not supported")
    cameras = camera_specs(
        (camera_key(obj), obj.name) for obj in scene.objects if obj.type == "CAMERA"
    )
    if not cameras:
        raise ValueError("The current scene has no cameras")
    scale = scene.render.resolution_percentage / 100.0
    channels = [Channel.BEAUTY]
    if include_alpha:
        channels.append(Channel.ALPHA)
    if include_object_id:
        channels.append(Channel.OBJECT_ID)
    blend_path = Path(bpy.data.filepath)
    engine = scene.render.engine
    engine_label = {
        "BLENDER_EEVEE_NEXT": "EEVEE",
        "CYCLES": "Cycles",
        "BLENDER_WORKBENCH": "Workbench",
    }.get(engine, engine)
    return RenderPlan(
        batch_number=batch_number,
        batch_label=format_batch(batch_number),
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
        conflict_policy=ConflictPolicy.NEXT_BATCH,
    )
