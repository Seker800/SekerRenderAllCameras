from __future__ import annotations

import bpy

from ..domain.naming import OUTPUT_DIRECTORY_NAME
from . import runtime_state


class RAC_UL_environment_pairs(bpy.types.UIList):
    def draw_item(
        self,
        _context: bpy.types.Context,
        layout: bpy.types.UILayout,
        _data: object,
        item: object,
        _icon: int,
        _active_data: object,
        _active_propname: str,
        _index: int,
    ) -> None:
        camera = item.camera
        layout.label(
            text=camera.name if camera is not None else "Choose Camera",
            icon="CAMERA_DATA",
        )


def draw_environment_pairs(
    layout: bpy.types.UILayout, settings: object, *, enabled: bool
) -> None:
    box = layout.box()
    box.enabled = enabled
    box.label(text="Camera Environments", icon="LIGHT")
    row = box.row()
    row.template_list(
        "RAC_UL_environment_pairs",
        "",
        settings,
        "environment_pairs",
        settings,
        "environment_pair_index",
        rows=2,
    )
    buttons = row.column(align=True)
    buttons.operator("render.camera_environment_pair_add", text="", icon="ADD")
    buttons.operator("render.camera_environment_pair_remove", text="", icon="REMOVE")
    if settings.environment_pairs:
        index = min(settings.environment_pair_index, len(settings.environment_pairs) - 1)
        item = settings.environment_pairs[index]
        details = box.column(align=True)
        details.prop(item, "camera")
        details.prop(item, "light_collection")
        details.prop(item, "world")
    else:
        box.label(text="Selecting a pair previews camera, lights, and World", icon="INFO")


def draw_controls(layout: bpy.types.UILayout, context: bpy.types.Context) -> None:
    settings = context.scene.rac_settings
    session = runtime_state.active_session
    row = layout.row(align=True)
    row.prop(settings, "include_alpha")
    row.prop(settings, "include_object_id")
    layout.prop(settings, "include_material_id")
    draw_environment_pairs(layout, settings, enabled=session is None)
    if session is None:
        layout.operator("render.render_all_cameras", icon="RENDER_STILL")
    else:
        layout.progress(factor=settings.progress, text=settings.status_text)
        if session.coordinator.snapshot().cancel_requested:
            layout.label(text="Waiting for current image…", icon="INFO")
        else:
            layout.operator("render.cancel_all_cameras", icon="CANCEL")
    layout.label(text=f"Output: //{OUTPUT_DIRECTORY_NAME}/", icon="FILE_FOLDER")


class RAC_PT_panel(bpy.types.Panel):
    bl_label = "Render All Cameras"
    bl_idname = "RAC_PT_render_all_cameras"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "output"

    def draw(self, context: bpy.types.Context) -> None:
        draw_controls(self.layout, context)


class RAC_PT_view3d_panel(bpy.types.Panel):
    bl_label = "Render All Cameras"
    bl_idname = "RAC_PT_view3d_render_all_cameras"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Batch Render"

    def draw(self, context: bpy.types.Context) -> None:
        draw_controls(self.layout, context)
