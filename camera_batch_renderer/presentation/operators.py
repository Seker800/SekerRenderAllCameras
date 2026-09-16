from __future__ import annotations

import bpy

from ..application import RENDER_CANCELLED, RENDER_COMPLETE
from ..blender.runtime import create_session
from . import runtime_state
from .host_policy import HOST_DRIVER_CLASS


def _render_complete(*_args: object) -> None:
    if runtime_state.active_session is not None:
        runtime_state.render_event = RENDER_COMPLETE


def _render_cancel(*_args: object) -> None:
    if runtime_state.active_session is not None:
        runtime_state.render_event = RENDER_CANCELLED


def _load_pre(*_args: object) -> None:
    session = runtime_state.active_session
    if session is not None:
        session.cancel()
        session.finish()
    driver = runtime_state.active_operator
    if driver is not None and hasattr(driver, "_remove_timer"):
        driver._remove_timer(bpy.context)
    runtime_state.clear()


def install_handlers() -> None:
    for handlers, callback in (
        (bpy.app.handlers.render_complete, _render_complete),
        (bpy.app.handlers.render_cancel, _render_cancel),
        (bpy.app.handlers.load_pre, _load_pre),
    ):
        if callback not in handlers:
            handlers.append(callback)


def remove_handlers() -> None:
    for handlers, callback in (
        (bpy.app.handlers.render_complete, _render_complete),
        (bpy.app.handlers.render_cancel, _render_cancel),
        (bpy.app.handlers.load_pre, _load_pre),
    ):
        if callback in handlers:
            handlers.remove(callback)


class RAC_OT_environment_pair_add(bpy.types.Operator):
    bl_idname = "render.camera_environment_pair_add"
    bl_label = "Add Camera Environment"
    bl_description = "Pair a camera with an optional light collection and World"

    @classmethod
    def poll(cls, _context: bpy.types.Context) -> bool:
        return runtime_state.active_session is None

    def execute(self, context: bpy.types.Context) -> set[str]:
        settings = context.scene.rac_settings
        settings.environment_pairs.add()
        settings.environment_pair_index = len(settings.environment_pairs) - 1
        return {"FINISHED"}


class RAC_OT_environment_pair_remove(bpy.types.Operator):
    bl_idname = "render.camera_environment_pair_remove"
    bl_label = "Remove Camera Environment"
    bl_description = "Remove the selected camera environment pairing"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return runtime_state.active_session is None and bool(
            context.scene.rac_settings.environment_pairs
        )

    def execute(self, context: bpy.types.Context) -> set[str]:
        settings = context.scene.rac_settings
        index = min(settings.environment_pair_index, len(settings.environment_pairs) - 1)
        settings.environment_pairs.remove(index)
        settings.environment_pair_index = max(0, min(index, len(settings.environment_pairs) - 1))
        return {"FINISHED"}


class RAC_OT_render_all(bpy.types.Operator):
    bl_idname = "render.render_all_cameras"
    bl_label = "Render All Cameras"
    bl_description = "Render a still image from every camera in the current scene"

    @classmethod
    def poll(cls, _context: bpy.types.Context) -> bool:
        return runtime_state.active_session is None and not bpy.app.is_job_running("RENDER")

    def execute(self, context: bpy.types.Context) -> set[str]:
        settings = context.scene.rac_settings
        try:
            session = create_session(
                context.scene,
                include_alpha=settings.include_alpha,
                include_object_id=settings.include_object_id,
                include_material_id=settings.include_material_id,
                environment_pairs=tuple(
                    (item.camera, item.light_collection, item.world)
                    for item in settings.environment_pairs
                ),
            )
            driver = HOST_DRIVER_CLASS(self, session)
            runtime_state.active_session = session
            runtime_state.active_operator = driver
            session.start()
        except Exception as exc:
            runtime_state.clear()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        settings.status_text = "Rendering"
        return driver.start(context)

    def modal(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        driver = runtime_state.active_operator
        if driver is None:
            return {"CANCELLED"}
        return driver.modal(context, event)

    def cancel(self, context: bpy.types.Context) -> None:
        session = runtime_state.active_session
        if session is not None:
            session.cancel()
        driver = runtime_state.active_operator
        if driver is not None:
            driver._finish(cancelled=True)


class RAC_OT_cancel(bpy.types.Operator):
    bl_idname = "render.cancel_all_cameras"
    bl_label = "Cancel Batch"
    bl_description = "Stop the batch after the image currently rendering is finished"

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = runtime_state.active_session
        if session is None:
            return {"CANCELLED"}
        session.coordinator.request_cancel()
        context.scene.rac_settings.status_text = "Stopping after current image"
        return {"FINISHED"}
