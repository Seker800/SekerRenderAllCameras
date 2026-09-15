from __future__ import annotations

from dataclasses import dataclass

import bpy


@dataclass(slots=True)
class BlenderStateTransaction:
    scene: bpy.types.Scene
    camera: bpy.types.Object | None = None
    filepath: str = ""
    frame: int = 0
    film_transparent: bool = False
    _restored: bool = False

    def capture(self) -> BlenderStateTransaction:
        self.camera = self.scene.camera
        self.filepath = self.scene.render.filepath
        self.frame = self.scene.frame_current
        self.film_transparent = self.scene.render.film_transparent
        return self

    def restore(self) -> None:
        if self._restored:
            return
        self.scene.camera = self.camera
        self.scene.render.filepath = self.filepath
        self.scene.frame_set(self.frame)
        self.scene.render.film_transparent = self.film_transparent
        self._restored = True

    def __enter__(self) -> BlenderStateTransaction:
        return self.capture()

    def __exit__(self, *_exc: object) -> None:
        self.restore()
