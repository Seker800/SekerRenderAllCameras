from __future__ import annotations

from pathlib import Path

import bpy

from .scene_reader import camera_key


class BlenderBeautyAdapter:
    def __init__(self, scene: bpy.types.Scene):
        self.scene = scene

    def prepare(self, requested_camera_key: str, output_path: Path) -> None:
        self.scene.camera = self.find_camera(requested_camera_key)
        self.scene.render.filepath = str(output_path)

    def find_camera(self, requested_camera_key: str) -> bpy.types.Object:
        for obj in self.scene.objects:
            if obj.type == "CAMERA" and camera_key(obj) == requested_camera_key:
                return obj
        raise LookupError(f"Camera no longer exists: {requested_camera_key}")

    def render_sync(self) -> None:
        bpy.ops.render.render(write_still=True, scene=self.scene.name)

    def render_async(self) -> set[str]:
        return bpy.ops.render.render("INVOKE_DEFAULT", write_still=True, scene=self.scene.name)
