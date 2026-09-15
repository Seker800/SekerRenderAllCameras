from __future__ import annotations

import bpy

from ..domain.naming import OUTPUT_DIRECTORY_NAME
from . import runtime_state


def draw_controls(layout: bpy.types.UILayout, context: bpy.types.Context) -> None:
    settings = context.scene.rac_settings
    row = layout.row(align=True)
    row.prop(settings, "include_alpha")
    row.prop(settings, "include_object_id")
    session = runtime_state.active_session
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
