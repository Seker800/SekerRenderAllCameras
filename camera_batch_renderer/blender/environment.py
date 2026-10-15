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


def set_layer_exclude(layer: bpy.types.LayerCollection, excluded: bool) -> None:
    if layer.exclude == excluded:
        return
    descendants = []
    pending = list(layer.children)
    while pending:
        child = pending.pop()
        descendants.append((child, child.exclude, child.hide_viewport))
        pending.extend(child.children)
    layer.exclude = excluded
    # Blender recursively changes child exclusions with the parent.
    for child, child_excluded, hidden in descendants:
        if child.exclude != child_excluded:
            child.exclude = child_excluded
        child.hide_viewport = hidden


def set_collection_visibility(
    scene: bpy.types.Scene,
    view_layer: bpy.types.ViewLayer,
    collection_key: str,
    *,
    enabled: bool,
    viewport: bool,
) -> None:
    """Change only the registered collection root; preserve manual descendants."""
    path = scene_collection_path(scene.collection, collection_key)
    if path is None:
        raise LookupError("Paired light collection is no longer in the current scene")
    collection = path[-1]
    collection.hide_render = not enabled
    if viewport:
        collection.hide_viewport = not enabled
    for layer in layer_collections(view_layer):
        if id_key(layer.collection) == collection_key:
            # Excluding a layer destroys its object Base data, including users'
            # per-object eye flags. Use collection visibility to hide presets.
            if enabled and layer.exclude:
                set_layer_exclude(layer, False)
            if viewport:
                layer.hide_viewport = not enabled


def switch_light_collections(
    scene: bpy.types.Scene,
    view_layer: bpy.types.ViewLayer,
    selected_key: str,
    registered_keys: tuple[str, ...],
    *,
    viewport: bool,
) -> None:
    # Ancestors must remain under manual control; hiding one would hide selected too.
    path = scene_collection_path(scene.collection, selected_key)
    if path is None:
        raise LookupError("Paired light collection is no longer in the current scene")
    ancestors = {id_key(item) for item in path[:-1]}
    for key in dict.fromkeys((*registered_keys, selected_key)):
        if key not in ancestors:
            set_collection_visibility(
                scene, view_layer, key, enabled=key == selected_key, viewport=viewport
            )


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
        switch_light_collections(
            scene,
            view_layer,
            id_key(light_collection),
            tuple(id_key(item) for item in other_light_collections),
            viewport=True,
        )
    if world is not None:
        scene.world = world
