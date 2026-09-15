from __future__ import annotations

import bpy

from . import runtime_state


class RAC_PT_panel(bpy.types.Panel):
    bl_label = "Render All Cameras"
    bl_idname = "RAC_PT_render_all_cameras"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "output"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        settings = context.scene.rac_settings
        layout.prop(settings, "batch_start")
        row = layout.row(align=True)
        row.prop(settings, "include_alpha")
        row.prop(settings, "include_object_id")
        if runtime_state.active_session is None:
            layout.operator("render.render_all_cameras", icon="RENDER_STILL")
        else:
            layout.progress(factor=settings.progress, text=settings.status_text)
            layout.operator("render.cancel_all_cameras", icon="CANCEL")
        layout.label(text="Output: //RenderOutput/<batch>/", icon="FILE_FOLDER")
