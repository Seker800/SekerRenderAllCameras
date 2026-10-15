from __future__ import annotations

import os
from pathlib import Path

import bpy

from ..application import RenderAction
from ..domain import CameraEnvironmentSpec, Channel
from .auxiliary import (
    AlphaScene,
    MaterialIdScene,
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
        self.auxiliary: AlphaScene | ObjectIdScene | MaterialIdScene | None = None
        self.id_colors = ()
        self.id_skipped: list[dict[str, str]] = []
        self.material_id_colors = ()
        self.material_id_names: dict[str, str] = {}
        self.material_id_skipped: list[dict[str, str]] = []
        self.last_beauty_path = None
        self.last_beauty_camera_key = None
        self.transaction = transaction
        self.environments = environments

    def prepare(self, action: RenderAction) -> bool:
        self.cleanup_auxiliary()
        staging_path = self.staging_path(action)
        staging_path.unlink(missing_ok=True)
        camera = self.find_camera(action.camera_key)
        self.transaction.apply_environment(
            self.environments.get(action.camera_key),
            tuple(
                env.light_collection_key
                for env in self.environments.values()
                if env.light_collection_key is not None
            ),
        )
        self.scene.camera = camera
        if action.channel is Channel.BEAUTY:
            self.last_beauty_path = None
            self.last_beauty_camera_key = None
            self.scene.camera = camera
            self.scene.render.filepath = str(staging_path)
            self.render_scene = self.scene
            return True
        if action.channel is Channel.ALPHA:
            if (
                self.scene.render.film_transparent
                and self._beauty_has_raw_alpha()
                and self.last_beauty_camera_key == action.camera_key
                and self.last_beauty_path is not None
                and self.last_beauty_path.exists()
            ):
                save_file_alpha(self.last_beauty_path, staging_path)
                return False
            self.auxiliary = AlphaScene(self.scene, camera, staging_path)
            self.render_scene = self.auxiliary.scene
            return True
        if action.channel is Channel.OBJECT_ID:
            self.auxiliary = ObjectIdScene(self.scene, camera, staging_path)
            self.render_scene = self.auxiliary.scene
            self.id_colors = self.auxiliary.colors
            self.id_skipped = self.auxiliary.skipped
            return True
        self.auxiliary = MaterialIdScene(self.scene, camera, staging_path)
        self.render_scene = self.auxiliary.scene
        self.material_id_colors = self.auxiliary.colors
        self.material_id_names = self.auxiliary.material_names
        self.material_id_skipped = self.auxiliary.skipped
        return True

    def _beauty_has_raw_alpha(self) -> bool:
        render = self.scene.render
        tree = getattr(self.scene, "compositing_node_group", None)
        if tree is None and getattr(self.scene, "use_nodes", False):
            tree = getattr(self.scene, "node_tree", None)
        compositing = getattr(render, "use_compositing", True) and tree is not None
        sequencer = render.use_sequencer and self.scene.sequence_editor is not None
        return (
            not compositing
            and not sequencer
            and render.image_settings.color_mode == "RGBA"
            and render.image_settings.file_format in {"PNG", "TIFF", "OPEN_EXR"}
        )

    def find_camera(self, requested_camera_key: str) -> bpy.types.Object:
        for obj in self.scene.objects:
            if obj.type == "CAMERA" and camera_key(obj) == requested_camera_key:
                return obj
        raise LookupError(f"Camera no longer exists: {requested_camera_key}")

    def render_sync(self) -> None:
        result = bpy.ops.render.render(write_still=True, scene=self.render_scene.name)
        if "FINISHED" not in result:
            raise RuntimeError(f"Blender render did not finish: {sorted(result)}")

    def show_render_view(self, display_type: str = "WINDOW") -> None:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "IMAGE_EDITOR":
                    image = area.spaces.active.image
                    if image is not None and image.type == "RENDER_RESULT":
                        return
        preferences = bpy.context.preferences.view
        original_display_type = preferences.render_display_type
        try:
            preferences.render_display_type = display_type
            # Open once, then let asynchronous jobs update this Render Result.
            bpy.ops.render.view_show("INVOKE_DEFAULT")
        finally:
            preferences.render_display_type = original_display_type

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
            # Native render windows can retain the auxiliary Scene. Detach UI
            # users before removing it, after the render job has stopped.
            for window in bpy.context.window_manager.windows:
                if window.scene == self.auxiliary.scene:
                    window.scene = self.scene
            self.auxiliary.cleanup()
            self.auxiliary = None
        self.render_scene = self.scene

    def finalize_output(self, action: RenderAction) -> None:
        staging_path = self.staging_path(action)
        if action.channel is Channel.ALPHA and isinstance(self.auxiliary, AlphaScene):
            replace_with_file_alpha(staging_path)
        elif action.channel is Channel.OBJECT_ID and self.id_colors:
            self.id_colors = self._calibrate_colors(staging_path, self.id_colors)
        elif action.channel is Channel.MATERIAL_ID and self.material_id_colors:
            self.material_id_colors = self._calibrate_colors(staging_path, self.material_id_colors)
        if not staging_path.is_file():
            raise RuntimeError(f"Render output was not written: {staging_path.name}")
        os.replace(staging_path, action.output_path)
        if action.channel is Channel.BEAUTY:
            self.last_beauty_path = action.output_path
            self.last_beauty_camera_key = action.camera_key

    def staging_path(self, action: RenderAction) -> Path:
        return self.staging_directory / action.output_path.name

    def has_fresh_output(self, action: RenderAction) -> bool:
        return self.staging_path(action).is_file()

    @staticmethod
    def _calibrate_colors(staging_path: Path, colors: tuple) -> tuple:
        actual = read_png_colors(staging_path) - {(0, 0, 0)}
        remaining = set(actual)
        calibrated = []
        for color in colors:
            if not remaining:
                calibrated.append(color)
                continue
            closest = min(
                remaining,
                key=lambda rgb: sum(
                    (left - right) ** 2 for left, right in zip(rgb, color.rgb, strict=True)
                ),
            )
            distance = sum(
                (left - right) ** 2 for left, right in zip(closest, color.rgb, strict=True)
            )
            if distance <= 16:
                calibrated.append(type(color)(color.key, closest))
                remaining.remove(closest)
            else:
                calibrated.append(color)
        return tuple(calibrated)


BlenderBeautyAdapter = BlenderRenderAdapter
