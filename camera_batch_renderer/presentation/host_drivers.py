from __future__ import annotations

from typing import Any

import bpy

from ..application import RENDER_CANCELLED, RENDER_COMPLETE, resolve_render_event
from ..blender.runtime import BlenderBatchSession
from . import runtime_state


class _DriverBase:
    def __init__(self, owner: bpy.types.Operator, session: BlenderBatchSession):
        self.owner = owner
        self.session = session

    @staticmethod
    def _update_progress(session: BlenderBatchSession) -> None:
        progress = session.coordinator.snapshot()
        session.scene.rac_settings.progress = len(progress.results) / max(
            1, progress.camera_count * len(session.coordinator.plan.channels)
        )

    def _finish(self, *, cancelled: bool) -> set[str]:
        session = self.session
        if runtime_state.active_session is session:
            if cancelled and not session.coordinator.is_finished:
                session.cancel()
            session.finish()
            status = session.coordinator.snapshot().status
            session.scene.rac_settings.status_text = status.value.replace("_", " ").title()
        self._remove_timer()
        runtime_state.clear()
        return {"CANCELLED"} if cancelled else {"FINISHED"}

    def _remove_timer(self, _context: bpy.types.Context | None = None) -> None:
        raise NotImplementedError


class ModalEventDriver(_DriverBase):
    """Blender 4.0/4.1 host loop: window-manager modal timer plus async renders."""

    def __init__(self, owner: bpy.types.Operator, session: BlenderBatchSession):
        super().__init__(owner, session)
        self._timer: bpy.types.Timer | None = None
        self._window: Any = None

    def start(self, context: bpy.types.Context) -> set[str]:
        self._window = context.window
        self._timer = context.window_manager.event_timer_add(0.15, window=context.window)
        context.window_manager.modal_handler_add(self.owner)
        try:
            self._start_next_render()
        except Exception as exc:
            self.session.fail_current(str(exc))
            return self._finish(cancelled=False)
        return {"RUNNING_MODAL"}

    def modal(self, _context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        session = runtime_state.active_session
        if session is not self.session:
            return self._finish(cancelled=True)
        action = session.coordinator.current_action
        resolved_event = resolve_render_event(
            runtime_state.render_event,
            render_job_running=bpy.app.is_job_running("RENDER"),
            output_exists=bool(action and session.adapter.has_fresh_output(action)),
        )
        if resolved_event == RENDER_CANCELLED:
            session.cancel()
            return self._finish(cancelled=True)
        if resolved_event != RENDER_COMPLETE:
            return {"PASS_THROUGH"}
        runtime_state.render_event = None
        session.complete_current()
        self._update_progress(session)
        try:
            if not self._start_next_render():
                return self._finish(cancelled=False)
        except Exception as exc:
            session.fail_current(str(exc))
            self.owner.report({"WARNING"}, f"Render item failed: {exc}")
            if not self._start_next_render():
                return self._finish(cancelled=False)
        return {"RUNNING_MODAL"}

    def _start_next_render(self) -> bool:
        session = self.session
        while session.coordinator.current_action is not None:
            if session.prepare_current():
                session.adapter.render_async()
                return True
            session.complete_current()
        return False

    def _remove_timer(self, context: bpy.types.Context | None = None) -> None:
        if self._timer is None:
            return
        window_manager = (
            context.window_manager if context is not None else bpy.context.window_manager
        )
        window_manager.event_timer_remove(self._timer)
        self._timer = None


class SynchronousTimerDriver(_DriverBase):
    """Newer host loop: one synchronous render per application-timer turn."""

    def __init__(self, owner: bpy.types.Operator, session: BlenderBatchSession):
        super().__init__(owner, session)
        self._callback = self._poll

    def start(self, _context: bpy.types.Context) -> set[str]:
        bpy.app.timers.register(self._callback, first_interval=0.1)
        return {"FINISHED"}

    def modal(self, _context: bpy.types.Context, _event: bpy.types.Event) -> set[str]:
        return {"FINISHED"}

    def _poll(self) -> float | None:
        if runtime_state.active_session is not self.session:
            return None
        session = self.session
        if session.coordinator.current_action is None:
            self._finish(cancelled=False)
            return None
        try:
            if session.prepare_current():
                session.adapter.render_sync()
            session.complete_current()
            self._update_progress(session)
        except Exception as exc:
            session.fail_current(str(exc))
            print(f"Render item failed: {exc}")
        if session.coordinator.current_action is None:
            self._finish(cancelled=False)
            return None
        return 0.1

    def _remove_timer(self, _context: bpy.types.Context | None = None) -> None:
        if bpy.app.timers.is_registered(self._callback):
            bpy.app.timers.unregister(self._callback)
