from __future__ import annotations

import time
from typing import Any

import bpy

from ..application import RENDER_CANCELLED, RENDER_COMPLETE, resolve_render_event
from ..blender.runtime import BatchIntegrityError, BlenderBatchSession
from . import runtime_state


class _DriverBase:
    def __init__(self, owner: bpy.types.Operator, session: BlenderBatchSession):
        self.owner = owner
        self.session = session
        self._after_finish = None

    def defer_shutdown(self, callback) -> None:
        """Keep the owning driver alive until the current native job releases its Scene."""
        self._after_finish = callback
        self.session.coordinator.request_cancel()

    @staticmethod
    def _update_progress(session: BlenderBatchSession) -> None:
        progress = session.coordinator.snapshot()
        session.scene.rac_settings.progress = len(progress.results) / max(
            1, progress.camera_count * len(session.coordinator.plan.channels)
        )

    def _finish(self, *, cancelled: bool) -> set[str]:
        session = self.session
        try:
            if runtime_state.active_session is session:
                try:
                    if cancelled and not session.coordinator.is_finished:
                        session.cancel()
                finally:
                    session.finish()
                progress = session.coordinator.snapshot()
                status = progress.status
                session.scene.rac_settings.status_text = status.value.replace("_", " ").title()
                if progress.error:
                    session.scene.rac_settings.status_text += f": {progress.error}"
        except Exception as exc:
            session.scene.rac_settings.status_text = f"Failed: {exc}"
            raise
        finally:
            self._remove_timer()
            runtime_state.clear()
            callback, self._after_finish = self._after_finish, None
            if callback is not None:
                callback()
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


class AsyncTimerDriver(_DriverBase):
    """Drive native render jobs without blocking UI or relying on window events."""

    display_type = "WINDOW"

    def __init__(self, owner: bpy.types.Operator, session: BlenderBatchSession):
        super().__init__(owner, session)
        self._callback = self._poll
        self._window = None
        self._waiting = False
        self._idle_since = None

    def start(self, context: bpy.types.Context) -> set[str]:
        self._window = context.window
        self.session.adapter.show_render_view(self.display_type)
        bpy.app.timers.register(self._callback, first_interval=0.1)
        return {"FINISHED"}

    def modal(self, _context: bpy.types.Context, _event: bpy.types.Event) -> set[str]:
        return {"FINISHED"}

    def _poll(self) -> float | None:
        try:
            return self._advance()
        except Exception as exc:
            # Manifest/transaction failures are batch failures, not another item.
            print(f"Batch failed: {exc}", flush=True)
            try:
                self.session.fail(str(exc))
            finally:
                self._finish_poll(cancelled=False)
            return None

    def _advance(self) -> float | None:
        if runtime_state.active_session is not self.session:
            return None
        session = self.session
        try:
            # A handler may fire before the host has released its render job.
            if bpy.app.is_job_running("RENDER"):
                session.record_diagnostic(
                    "rendering", heartbeat=True, native_event=runtime_state.render_event
                )
                self._idle_since = None
                return 0.15
            if self._waiting:
                session.record_diagnostic(
                    "waiting_for_completion", heartbeat=True,
                    native_event=runtime_state.render_event,
                )
                action = session.coordinator.current_action
                resolved = resolve_render_event(
                    runtime_state.render_event,
                    render_job_running=False,
                    output_exists=session.adapter.has_fresh_output(action),
                )
                if resolved == RENDER_CANCELLED:
                    return self._finish_poll(cancelled=True)
                if resolved == RENDER_COMPLETE:
                    self._waiting = False
                    runtime_state.render_event = None
                    session.complete_current()
                    self._update_progress(session)
                    # Start next on another timer turn, outside terminal handling.
                    return 0.15
                # Only bound time spent IDLE without a terminal signal or file.
                # Long Cycles renders have no duration limit while the job is active.
                now = time.monotonic()
                if self._idle_since is None:
                    self._idle_since = now
                if now - self._idle_since < 2.0:
                    return 0.15
                raise RuntimeError("Blender render job ended without an output or completion event")
            if session.coordinator.current_action is None:
                return self._finish_poll(cancelled=False)
            if session.coordinator.snapshot().cancel_requested:
                return self._finish_poll(cancelled=True)
            runtime_state.render_event = None
            action = session.coordinator.current_action
            session.scene.rac_settings.status_text = f"{action.channel.value}: {action.camera_name}"
            if session.prepare_current():
                # Render windows change the global context. Always launch from
                # the original scene window; never inherit the result window.
                if self._window not in bpy.context.window_manager.windows[:]:
                    raise RuntimeError("The batch render's scene window was closed")
                with bpy.context.temp_override(window=self._window):
                    if session.adapter.render_scene.render.engine == "BLENDER_WORKBENCH":
                        # Workbench uses the window's GPU context. Running it on
                        # an async job can crash older Windows GL drivers.
                        session.adapter.render_sync()
                        session.complete_current()
                        self._update_progress(session)
                        return 0.15
                    session.adapter.render_async()
                session.record_diagnostic("render_submitted")
                self._waiting = True
                self._idle_since = None
            else:
                session.complete_current()
                self._update_progress(session)
        except BatchIntegrityError:
            raise
        except Exception as exc:
            self._waiting = False
            runtime_state.render_event = None
            session.fail_current(str(exc))
            self._update_progress(session)
            print(f"Render item failed: {exc}", flush=True)
        return 0.15

    def _finish_poll(self, *, cancelled: bool) -> None:
        self._finish(cancelled=cancelled)
        return None

    def _remove_timer(self, _context: bpy.types.Context | None = None) -> None:
        if bpy.app.timers.is_registered(self._callback):
            bpy.app.timers.unregister(self._callback)
