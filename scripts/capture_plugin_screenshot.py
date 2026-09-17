from __future__ import annotations

import os
import traceback
from importlib import import_module
from pathlib import Path

import bpy

_target_area: bpy.types.Area | None = None


def configure_panel() -> bpy.types.Area:
    scene = bpy.context.scene
    if not hasattr(scene, "rac_settings"):
        bpy.ops.preferences.addon_enable(module="bl_ext.user_default.camera_batch_renderer")
    settings = scene.rac_settings
    settings.include_beauty = True
    settings.include_alpha = True
    settings.include_object_id = True
    settings.include_material_id = True
    if not settings.environment_pairs:
        pair = settings.environment_pairs.add()
        pair.camera = scene.camera
        light = next((obj for obj in scene.objects if obj.type == "LIGHT"), None)
        light_collection = bpy.data.collections.new("Studio Lights")
        scene.collection.children.link(light_collection)
        if light is not None:
            light_collection.objects.link(light)
        pair.light_collection = light_collection
        pair.world = scene.world
        settings.environment_pair_index = 0
    area = max(
        (item for item in bpy.context.screen.areas if item.type == "VIEW_3D"),
        key=lambda item: item.width * item.height,
    )
    panel_module = import_module("bl_ext.user_default.camera_batch_renderer.presentation.panel")
    panel_class = panel_module.RAC_PT_view3d_panel
    bpy.utils.unregister_class(panel_class)
    panel_class.bl_category = "Item"
    bpy.utils.register_class(panel_class)
    area.spaces.active.show_region_ui = True
    area.tag_redraw()
    return area


def capture() -> None:
    try:
        output = Path(os.environ["RAC_SCREENSHOT_PATH"]).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        if _target_area is None:
            raise RuntimeError("Screenshot area is not configured")
        area = _target_area
        with bpy.context.temp_override(window=bpy.context.window, area=area):
            result = bpy.ops.screen.screenshot_area(
                filepath=str(output),
                hide_props_region=False,
                check_existing=False,
            )
        if result != {"FINISHED"}:
            raise RuntimeError(f"Screenshot failed: {result}")
        regions = [
            {
                "type": region.type,
                "x": region.x,
                "y": region.y,
                "width": region.width,
                "height": region.height,
            }
            for region in area.regions
        ]
        print(
            "PLUGIN_SCREENSHOT_OK",
            {"path": str(output), "area": (area.width, area.height), "regions": regions},
            flush=True,
        )
    except Exception:
        traceback.print_exc()
        os._exit(1)
    bpy.ops.wm.quit_blender()


def prepare() -> None:
    global _target_area
    try:
        _target_area = configure_panel()
        bpy.app.timers.register(capture, first_interval=1.0)
    except Exception:
        traceback.print_exc()
        os._exit(1)


bpy.app.timers.register(prepare, first_interval=1.0)
