from __future__ import annotations

import bpy

from ..application import RenderAction
from ..domain import Channel
from .auxiliary import (
    AlphaScene,
    ObjectIdScene,
    read_png_colors,
    replace_with_file_alpha,
    save_file_alpha,
)
from .scene_reader import camera_key


class BlenderRenderAdapter:
    def __init__(self, scene: bpy.types.Scene):
        self.scene = scene
        self.render_scene = scene
        self.auxiliary: AlphaScene | ObjectIdScene | None = None
        self.id_colors = ()
        self.id_skipped: list[dict[str, str]] = []
        self.last_beauty_path = None

    def prepare(self, action: RenderAction) -> bool:
        self.cleanup_auxiliary()
        camera = self.find_camera(action.camera_key)
        if action.channel is Channel.BEAUTY:
            self.scene.camera = camera
            self.scene.render.filepath = str(action.output_path)
            self.render_scene = self.scene
            self.last_beauty_path = action.output_path
            return True
        if action.channel is Channel.ALPHA:
            if self.scene.render.film_transparent:
                if self.last_beauty_path is None or not self.last_beauty_path.exists():
                    raise RuntimeError("Beauty output is unavailable for Alpha extraction")
                save_file_alpha(self.last_beauty_path, action.output_path)
                return False
            self.auxiliary = AlphaScene(self.scene, camera, action.output_path)
            self.render_scene = self.auxiliary.scene
            return True
        self.auxiliary = ObjectIdScene(self.scene, camera, action.output_path)
        self.render_scene = self.auxiliary.scene
        self.id_colors = self.auxiliary.colors
        self.id_skipped = self.auxiliary.skipped
        return True

    def find_camera(self, requested_camera_key: str) -> bpy.types.Object:
        for obj in self.scene.objects:
            if obj.type == "CAMERA" and camera_key(obj) == requested_camera_key:
                return obj
        raise LookupError(f"Camera no longer exists: {requested_camera_key}")

    def render_sync(self) -> None:
        bpy.ops.render.render(write_still=True, scene=self.render_scene.name)

    def render_async(self) -> set[str]:
        return bpy.ops.render.render(
            "INVOKE_DEFAULT", write_still=True, scene=self.render_scene.name
        )

    def cleanup_auxiliary(self) -> None:
        if self.auxiliary is not None:
            self.auxiliary.cleanup()
            self.auxiliary = None
        self.render_scene = self.scene

    def finalize_output(self, action: RenderAction) -> None:
        if action.channel is Channel.ALPHA and isinstance(self.auxiliary, AlphaScene):
            replace_with_file_alpha(action.output_path)
            return
        if action.channel is not Channel.OBJECT_ID or not self.id_colors:
            return
        actual = read_png_colors(action.output_path) - {(0, 0, 0)}
        remaining = set(actual)
        calibrated = []
        for color in self.id_colors:
            if not remaining:
                calibrated.append(color)
                continue
            closest = min(
                remaining,
                key=lambda rgb: sum(
                    (left - right) ** 2 for left, right in zip(rgb, color.rgb, strict=True)
                ),
            )
            if (
                sum((left - right) ** 2 for left, right in zip(closest, color.rgb, strict=True))
                <= 16
            ):
                calibrated.append(type(color)(color.key, closest))
                remaining.remove(closest)
            else:
                calibrated.append(color)
        self.id_colors = tuple(calibrated)


BlenderBeautyAdapter = BlenderRenderAdapter
