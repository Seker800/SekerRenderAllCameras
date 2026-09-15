from __future__ import annotations

import bpy

from . import runtime_state
from .operators import RAC_OT_cancel, RAC_OT_render_all, install_handlers, remove_handlers
from .panel import RAC_PT_panel
from .properties import RAC_Settings

CLASSES = (RAC_Settings, RAC_OT_render_all, RAC_OT_cancel, RAC_PT_panel)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rac_settings = bpy.props.PointerProperty(type=RAC_Settings)
    install_handlers()


def unregister() -> None:
    session = runtime_state.active_session
    operator = runtime_state.active_operator
    if session is not None:
        session.cancel()
        session.finish()
    if operator is not None and hasattr(operator, "_remove_timer"):
        operator._remove_timer(bpy.context)
    runtime_state.clear()
    remove_handlers()
    if hasattr(bpy.types.Scene, "rac_settings"):
        del bpy.types.Scene.rac_settings
    for cls in reversed(CLASSES):
        if getattr(cls, "is_registered", False):
            bpy.utils.unregister_class(cls)
