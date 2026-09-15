from __future__ import annotations

import bpy

from . import runtime_state
from .operators import RAC_OT_cancel, RAC_OT_render_all
from .panel import RAC_PT_panel
from .properties import RAC_Settings

CLASSES = (RAC_Settings, RAC_OT_render_all, RAC_OT_cancel, RAC_PT_panel)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rac_settings = bpy.props.PointerProperty(type=RAC_Settings)


def unregister() -> None:
    session = runtime_state.active_session
    if session is not None:
        session.coordinator.request_cancel()
        session.finish()
    runtime_state.clear()
    if hasattr(bpy.types.Scene, "rac_settings"):
        del bpy.types.Scene.rac_settings
    for cls in reversed(CLASSES):
        if getattr(cls, "is_registered", False):
            bpy.utils.unregister_class(cls)
