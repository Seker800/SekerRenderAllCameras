import bpy


def _preview_pair(pair: object, context: bpy.types.Context | None) -> None:
    if context is None or context.scene is None or context.view_layer is None:
        return
    from . import runtime_state

    if runtime_state.active_session is not None:
        return
    settings = context.scene.rac_settings
    try:
        from ..blender.environment import preview_environment

        preview_environment(
            context.scene,
            context.view_layer,
            camera=pair.camera,
            light_collection=pair.light_collection,
            world=pair.world,
            other_light_collections=tuple(
                item.light_collection
                for item in settings.environment_pairs
                if item.as_pointer() != pair.as_pointer()
                and item.light_collection is not None
            ),
        )
    except Exception as exc:
        settings.status_text = f"Environment preview failed: {exc}"
    else:
        settings.status_text = "Environment preview updated"


def _pair_updated(pair: object, context: bpy.types.Context) -> None:
    settings = context.scene.rac_settings
    if not settings.environment_pairs:
        return
    index = min(settings.environment_pair_index, len(settings.environment_pairs) - 1)
    if settings.environment_pairs[index].as_pointer() == pair.as_pointer():
        _preview_pair(pair, context)


def _active_pair_updated(settings: object, context: bpy.types.Context) -> None:
    if not settings.environment_pairs:
        return
    index = min(settings.environment_pair_index, len(settings.environment_pairs) - 1)
    _preview_pair(settings.environment_pairs[index], context)


def _camera_poll(_self: object, obj: bpy.types.Object) -> bool:
    return obj.type == "CAMERA"


class RAC_EnvironmentPair(bpy.types.PropertyGroup):
    camera: bpy.props.PointerProperty(
        name="Camera",
        type=bpy.types.Object,
        poll=_camera_poll,
        update=_pair_updated,
    )
    light_collection: bpy.props.PointerProperty(
        name="Light Collection",
        type=bpy.types.Collection,
        description="Only lights in this collection and its child collections will render",
        update=_pair_updated,
    )
    world: bpy.props.PointerProperty(
        name="World",
        type=bpy.types.World,
        description="World used while rendering this camera",
        update=_pair_updated,
    )


class RAC_Settings(bpy.types.PropertyGroup):
    include_beauty: bpy.props.BoolProperty(name="Render Beauty", default=True)
    include_alpha: bpy.props.BoolProperty(name="Render Alpha", default=False)
    include_object_id: bpy.props.BoolProperty(name="Render Object ID", default=False)
    include_material_id: bpy.props.BoolProperty(name="Render Material ID", default=False)
    status_text: bpy.props.StringProperty(name="Status", default="Ready")
    progress: bpy.props.FloatProperty(name="Progress", default=0.0, min=0.0, max=1.0)
    environment_pairs: bpy.props.CollectionProperty(type=RAC_EnvironmentPair)
    environment_pair_index: bpy.props.IntProperty(
        default=0,
        min=0,
        update=_active_pair_updated,
    )
