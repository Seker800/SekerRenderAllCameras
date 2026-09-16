from __future__ import annotations

import bpy


def id_key(item: bpy.types.ID) -> str:
    library = item.library.filepath if item.library else "local"
    return f"{library}|{item.name_full}"


def collection_tree(collection: bpy.types.Collection) -> tuple[bpy.types.Collection, ...]:
    result: list[bpy.types.Collection] = []
    pending = [collection]
    while pending:
        current = pending.pop()
        result.append(current)
        pending.extend(current.children)
    return tuple(result)


def collection_lights(collection: bpy.types.Collection) -> tuple[bpy.types.Object, ...]:
    lights: dict[str, bpy.types.Object] = {}
    for current in collection_tree(collection):
        for obj in current.objects:
            if obj.type == "LIGHT":
                lights[id_key(obj)] = obj
    return tuple(lights[key] for key in sorted(lights))


def scene_collection_path(
    root: bpy.types.Collection, target_key: str
) -> tuple[bpy.types.Collection, ...] | None:
    pending = [(root, (root,))]
    while pending:
        current, path = pending.pop()
        if id_key(current) == target_key:
            return path
        pending.extend((child, (*path, child)) for child in current.children)
    return None


def layer_collections(
    view_layer: bpy.types.ViewLayer,
) -> tuple[bpy.types.LayerCollection, ...]:
    result: list[bpy.types.LayerCollection] = []
    pending = [view_layer.layer_collection]
    while pending:
        current = pending.pop()
        result.append(current)
        pending.extend(current.children)
    return tuple(result)


def _reveal_layer_subtree(
    layer_collection: bpy.types.LayerCollection, *, viewport: bool
) -> None:
    layer_collection.exclude = False
    if viewport:
        layer_collection.hide_viewport = False
    for child in layer_collection.children:
        _reveal_layer_subtree(child, viewport=viewport)


def _reveal_layer_path(
    layer_collection: bpy.types.LayerCollection,
    target_key: str,
    *,
    viewport: bool,
) -> bool:
    if id_key(layer_collection.collection) == target_key:
        _reveal_layer_subtree(layer_collection, viewport=viewport)
        return True
    for child in layer_collection.children:
        if _reveal_layer_path(child, target_key, viewport=viewport):
            layer_collection.exclude = False
            if viewport:
                layer_collection.hide_viewport = False
            return True
    return False


def reveal_collection(
    scene: bpy.types.Scene,
    view_layer: bpy.types.ViewLayer,
    collection_key: str,
    *,
    viewport: bool,
) -> bpy.types.Collection:
    path = scene_collection_path(scene.collection, collection_key)
    if path is None:
        raise LookupError("Paired light collection is no longer in the current scene")
    for collection in path:
        collection.hide_render = False
        if viewport:
            collection.hide_viewport = False
    for collection in collection_tree(path[-1]):
        collection.hide_render = False
        if viewport:
            collection.hide_viewport = False
    if not _reveal_layer_path(
        view_layer.layer_collection, collection_key, viewport=viewport
    ):
        raise LookupError("Paired light collection is unavailable in the current view layer")
    return path[-1]


def hide_collection(
    scene: bpy.types.Scene,
    view_layer: bpy.types.ViewLayer,
    collection_key: str,
) -> None:
    path = scene_collection_path(scene.collection, collection_key)
    if path is None:
        return
    collection = path[-1]
    collection.hide_render = True
    collection.hide_viewport = True
    for layer_collection in layer_collections(view_layer):
        if id_key(layer_collection.collection) == collection_key:
            layer_collection.exclude = True


def isolate_lights(
    scene: bpy.types.Scene,
    allowed_keys: set[str],
    *,
    viewport: bool,
    view_layer: bpy.types.ViewLayer | None = None,
) -> None:
    for obj in scene.objects:
        if obj.type != "LIGHT":
            continue
        enabled = id_key(obj) in allowed_keys
        obj.hide_render = not enabled
        if viewport:
            obj.hide_viewport = not enabled
            try:
                obj.hide_set(not enabled, view_layer=view_layer)
            except RuntimeError:
                # An excluded collection removes the object from this View Layer.
                pass


def preview_environment(
    scene: bpy.types.Scene,
    view_layer: bpy.types.ViewLayer,
    *,
    camera: bpy.types.Object | None,
    light_collection: bpy.types.Collection | None,
    world: bpy.types.World | None,
    other_light_collections: tuple[bpy.types.Collection, ...] = (),
) -> None:
    if camera is not None:
        scene.camera = camera
    if light_collection is not None:
        key = id_key(light_collection)
        reveal_collection(scene, view_layer, key, viewport=True)
        isolate_lights(
            scene,
            {id_key(light) for light in collection_lights(light_collection)},
            viewport=True,
            view_layer=view_layer,
        )
        for other in other_light_collections:
            other_key = id_key(other)
            if other_key != key:
                hide_collection(scene, view_layer, other_key)
    if world is not None:
        scene.world = world
