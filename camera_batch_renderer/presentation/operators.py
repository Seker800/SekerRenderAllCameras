from __future__ import annotations

import traceback

import bpy
from bpy.app.handlers import persistent

from ..application import RENDER_CANCELLED, RENDER_COMPLETE
from ..blender.diagnostics import begin_diagnostics
from ..blender.runtime import create_session
from . import runtime_state
from .host_policy import HOST_DRIVER_CLASS


@persistent
def _render_complete(*_args: object) -> None:
    session = runtime_state.active_session
    if session is not None and _args and _args[0] == session.adapter.render_scene:
        runtime_state.render_event = RENDER_COMPLETE


@persistent
def _render_cancel(*_args: object) -> None:
    session = runtime_state.active_session
    if session is not None and _args and _args[0] == session.adapter.render_scene:
        runtime_state.render_event = RENDER_CANCELLED


@persistent
def _load_pre(*_args: object) -> None:
    session = runtime_state.active_session
    driver = runtime_state.active_operator
    if driver is not None:
        driver._finish(cancelled=True)
    elif session is not None:
        session.cancel()
        session.finish()
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
        if runtime_state.active_session is not None:
            cls.poll_message_set("A batch is already running")
            return False
        if bpy.app.is_job_running("RENDER"):
            cls.poll_message_set("Wait for the current Blender render to finish")
            return False
        return True

    def execute(self, context: bpy.types.Context) -> set[str]:
        settings = context.scene.rac_settings
        session = None
        driver = None
        diagnostics = None
        try:
            diagnostics = begin_diagnostics(context.scene, {
                "Beauty": settings.include_beauty,
                "Alpha": settings.include_alpha,
                "ObjectID": settings.include_object_id,
                "MaterialID": settings.include_material_id,
            })
        except Exception as exc:
            settings.diagnostic_error = f"Cannot collect diagnostics: {exc}"
        try:
            session = create_session(
                context.scene,
                include_beauty=settings.include_beauty,
                include_alpha=settings.include_alpha,
                include_object_id=settings.include_object_id,
                include_material_id=settings.include_material_id,
                diagnostics=diagnostics,
                environment_pairs=tuple(
                    (item.camera, item.light_collection, item.world)
                    for item in settings.environment_pairs
                ),
            )
            driver = HOST_DRIVER_CLASS(self, session)
            runtime_state.active_session = session
            runtime_state.active_operator = driver
            session.start()
            settings.status_text = "Preparing render"
            settings.progress = 0.0
            return driver.start(context)
        except Exception as exc:
            message = str(exc)
            if diagnostics is not None:
                diagnostics.record("start_failed", error=message, traceback=traceback.format_exc())
            try:
                if driver is not None:
                    driver._remove_timer(context)
                if session is not None:
                    message = session.abort_start(message)
            finally:
                runtime_state.clear()
            settings.status_text = f"Cannot start: {message}"
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

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
        session.scene.rac_settings.status_text = "Stopping after current image"
        return {"FINISHED"}
