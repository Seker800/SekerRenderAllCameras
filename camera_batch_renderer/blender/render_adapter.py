from __future__ import annotations

import os
from pathlib import Path

import bpy

from ..application import RenderAction
from ..domain import CameraEnvironmentSpec, Channel
from .auxiliary import (
    AlphaScene,
    ObjectIdScene,
    read_png_colors,
    replace_with_file_alpha,
    save_file_alpha,
)
from .scene_reader import camera_key
from .state_transaction import BlenderStateTransaction


class BlenderRenderAdapter:
    def __init__(
        self,
        scene: bpy.types.Scene,
        staging_directory: Path,
        transaction: BlenderStateTransaction,
        environments: dict[str, CameraEnvironmentSpec],
    ):
        self.scene = scene
        self.staging_directory = staging_directory
        self.render_scene = scene
        self.auxiliary: AlphaScene | ObjectIdScene | None = None
        self.id_colors = ()
        self.id_skipped: list[dict[str, str]] = []
        self.last_beauty_path = None
        self.transaction = transaction
        self.environments = environments

    def prepare(self, action: RenderAction) -> bool:
        self.cleanup_auxiliary()
        staging_path = self.staging_path(action)
        staging_path.unlink(missing_ok=True)
        camera = self.find_camera(action.camera_key)
        self.transaction.apply_environment(self.environments.get(action.camera_key))
        if action.channel is Channel.BEAUTY:
            self.scene.camera = camera
            self.scene.render.filepath = str(staging_path)
            self.render_scene = self.scene
            self.last_beauty_path = action.output_path
            return True
        if action.channel is Channel.ALPHA:
            if self.scene.render.film_transparent:
                if self.last_beauty_path is None or not self.last_beauty_path.exists():
                    raise RuntimeError("Beauty output is unavailable for Alpha extraction")
                save_file_alpha(self.last_beauty_path, staging_path)
                return False
            self.auxiliary = AlphaScene(self.scene, camera, staging_path)
            self.render_scene = self.auxiliary.scene
            return True
        self.auxiliary = ObjectIdScene(self.scene, camera, staging_path)
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
        preferences = bpy.context.preferences.view
        render_display_type = preferences.render_display_type
        try:
            preferences.render_display_type = "NONE"
            result = bpy.ops.render.render(
                "INVOKE_DEFAULT", write_still=True, scene=self.render_scene.name
            )
        finally:
            preferences.render_display_type = render_display_type
        if "RUNNING_MODAL" not in result:
            statuses = ", ".join(sorted(result)) or "no status"
            raise RuntimeError(f"Blender did not start the render ({statuses})")
        return result

    def cleanup_auxiliary(self) -> None:
        if self.auxiliary is not None:
            self.auxiliary.cleanup()
            self.auxiliary = None
        self.render_scene = self.scene

    def finalize_output(self, action: RenderAction) -> None:
        staging_path = self.staging_path(action)
        if action.channel is Channel.ALPHA and isinstance(self.auxiliary, AlphaScene):
            replace_with_file_alpha(staging_path)
        elif action.channel is Channel.OBJECT_ID and self.id_colors:
            actual = read_png_colors(staging_path) - {(0, 0, 0)}
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
                    sum(
                        (left - right) ** 2
                        for left, right in zip(closest, color.rgb, strict=True)
                    )
                    <= 16
                ):
                    calibrated.append(type(color)(color.key, closest))
                    remaining.remove(closest)
                else:
                    calibrated.append(color)
            self.id_colors = tuple(calibrated)
        if not staging_path.is_file():
            raise RuntimeError(f"Render output was not written: {staging_path.name}")
        os.replace(staging_path, action.output_path)

    def staging_path(self, action: RenderAction) -> Path:
        return self.staging_directory / action.output_path.name

    def has_fresh_output(self, action: RenderAction) -> bool:
        return self.staging_path(action).is_file()


BlenderBeautyAdapter = BlenderRenderAdapter
