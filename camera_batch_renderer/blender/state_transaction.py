from __future__ import annotations

from dataclasses import dataclass, field

import bpy

from ..domain import CameraEnvironmentSpec
from .environment import (
    collection_tree,
    id_key,
    layer_collections,
    set_layer_exclude,
    switch_light_collections,
)


@dataclass(slots=True)
class BlenderStateTransaction:
    scene: bpy.types.Scene
    camera: bpy.types.Object | None = None
    filepath: str = ""
    frame: int = 0
    subframe: float = 0.0
    film_transparent: bool = False
    world: bpy.types.World | None = None
    light_hide_render: dict[str, tuple[bpy.types.Object, bool]] | None = None
    collection_hide_render: list[tuple[bpy.types.Collection, bool]] | None = None
    layer_exclude: list[tuple[bpy.types.LayerCollection, bool]] | None = None
    _modified_collection_keys: set[str] = field(default_factory=set)
    _restored: bool = False

    def capture(self) -> BlenderStateTransaction:
        self.camera = self.scene.camera
        self.filepath = self.scene.render.filepath
        self.frame = self.scene.frame_current
        self.subframe = self.scene.frame_subframe
        self.film_transparent = self.scene.render.film_transparent
        self.world = self.scene.world
        self.light_hide_render = {
            id_key(obj): (obj, bool(obj.hide_render))
            for obj in self.scene.objects
            if obj.type == "LIGHT"
        }
        self.collection_hide_render = [
            (collection, bool(collection.hide_render))
            for collection in collection_tree(self.scene.collection)
        ]
        self.layer_exclude = [
            (layer_collection, bool(layer_collection.exclude))
            for view_layer in self.scene.view_layers
            for layer_collection in layer_collections(view_layer)
        ]
        return self

    def _restore_environment_baseline(self) -> None:
        self.scene.world = self.world
        if self.collection_hide_render is not None:
            for collection, hidden in self.collection_hide_render:
                if id_key(collection) in self._modified_collection_keys:
                    collection.hide_render = hidden
        if self.layer_exclude is not None:
            for layer_collection, excluded in self.layer_exclude:
                if id_key(layer_collection.collection) in self._modified_collection_keys:
                    set_layer_exclude(layer_collection, excluded)

    def apply_environment(
        self,
        environment: CameraEnvironmentSpec | None,
        registered_collection_keys: tuple[str, ...] = (),
    ) -> None:
        if self.light_hide_render is None:
            raise RuntimeError("Blender state was not captured")
        self._restore_environment_baseline()
        if environment is None:
            return
        if environment.light_object_keys is not None:
            requested = set(environment.light_object_keys)
            missing = requested - self.light_hide_render.keys()
            if missing:
                raise LookupError("One or more paired lights no longer exist in the scene")
            if environment.light_collection_key is None:
                raise RuntimeError("Paired light collection key is missing")
            self._modified_collection_keys.update(
                (*registered_collection_keys, environment.light_collection_key)
            )
            for view_layer in self.scene.view_layers:
                switch_light_collections(
                    self.scene,
                    view_layer,
                    environment.light_collection_key,
                    registered_collection_keys,
                    viewport=False,
                )
        if environment.world_key is not None:
            for world in bpy.data.worlds:
                if id_key(world) == environment.world_key:
                    self.scene.world = world
                    break
            else:
                raise LookupError(f"Paired World no longer exists: {environment.world_name}")

    def restore(self) -> None:
        if self._restored:
            return
        self.scene.camera = self.camera
        self.scene.render.filepath = self.filepath
        self.scene.frame_set(self.frame, subframe=self.subframe)
        self.scene.render.film_transparent = self.film_transparent
        try:
            self._restore_environment_baseline()
        except ReferenceError:
            pass
        self._restored = True

    def __enter__(self) -> BlenderStateTransaction:
        return self.capture()

    def __exit__(self, *_exc: object) -> None:
        self.restore()
