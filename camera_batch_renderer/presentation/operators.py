from __future__ import annotations

import bpy

from ..blender.runtime import BlenderBatchSession, create_session
from ..domain import BatchStatus
from . import runtime_state


def _render_complete(*_args: object) -> None:
    if runtime_state.active_session is not None:
        runtime_state.render_event = "complete"


def _render_cancel(*_args: object) -> None:
    if runtime_state.active_session is not None:
        runtime_state.render_event = "cancelled"


def _load_pre(*_args: object) -> None:
    session = runtime_state.active_session
    if session is not None:
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


class RAC_OT_render_all(bpy.types.Operator):
    bl_idname = "render.render_all_cameras"
    bl_label = "Render All Cameras"
    bl_description = "Render a still image from every camera in the current scene"

    _timer: bpy.types.Timer | None = None

    @classmethod
    def poll(cls, _context: bpy.types.Context) -> bool:
        return runtime_state.active_session is None and not bpy.app.is_job_running("RENDER")

    def execute(self, context: bpy.types.Context) -> set[str]:
        settings = context.scene.rac_settings
        try:
            session = create_session(
                context.scene,
                batch_start=settings.batch_start,
                include_alpha=settings.include_alpha,
                include_object_id=settings.include_object_id,
            )
            runtime_state.active_session = session
            runtime_state.active_operator = self
            session.start()
        except Exception as exc:
            runtime_state.clear()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self._timer = context.window_manager.event_timer_add(0.15, window=context.window)
        context.window_manager.modal_handler_add(self)
        settings.status_text = "Rendering"
        try:
            self._start_next_render(session)
        except Exception as exc:
            session.fail_current(str(exc))
            return self._finish(context, cancelled=False)
        return {"RUNNING_MODAL"}

    def modal(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        session = runtime_state.active_session
        if session is None:
            return self._finish(context, cancelled=True)
        if runtime_state.render_event == "cancelled":
            session.cancel()
            return self._finish(context, cancelled=True)
        if runtime_state.render_event != "complete":
            return {"PASS_THROUGH"}
        runtime_state.render_event = None
        session.complete_current()
        self._update_progress(context, session)
        try:
            if not self._start_next_render(session):
                return self._finish(context, cancelled=False)
        except Exception as exc:
            session.fail_current(str(exc))
            self.report({"WARNING"}, f"Render item failed: {exc}")
            if not self._start_next_render(session):
                return self._finish(context, cancelled=False)
        return {"RUNNING_MODAL"}

    @staticmethod
    def _start_next_render(session: BlenderBatchSession) -> bool:
        while session.coordinator.current_action is not None:
            if session.prepare_current():
                session.adapter.render_async()
                return True
            session.complete_current()
        return False

    @staticmethod
    def _update_progress(context: bpy.types.Context, session: BlenderBatchSession) -> None:
        progress = session.coordinator.snapshot()
        context.scene.rac_settings.progress = len(progress.results) / max(
            1, progress.camera_count * len(session.coordinator.plan.channels)
        )

    def cancel(self, context: bpy.types.Context) -> None:
        session = runtime_state.active_session
        if session is not None:
            session.cancel()
        self._finish(context, cancelled=True)

    def _finish(self, context: bpy.types.Context, *, cancelled: bool) -> set[str]:
        session = runtime_state.active_session
        if session is not None:
            if cancelled and not session.coordinator.is_finished:
                session.cancel()
            session.finish()
            status = session.coordinator.snapshot().status
            context.scene.rac_settings.status_text = status.value.replace("_", " ").title()
            if status is BatchStatus.COMPLETED:
                context.scene.rac_settings.batch_start = session.allocation.number + 1
        self._remove_timer(context)
        runtime_state.clear()
        return {"CANCELLED"} if cancelled else {"FINISHED"}

    def _remove_timer(self, context: bpy.types.Context) -> None:
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


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
        if not bpy.app.is_job_running("RENDER"):
            runtime_state.render_event = "cancelled"
        return {"FINISHED"}
