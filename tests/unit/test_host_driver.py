from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from camera_batch_renderer import application
from camera_batch_renderer.domain import BatchStatus


class HostDriverTests(unittest.TestCase):
    def setUp(self):
        # Load the real driver with a minimal host, without registering Blender UI.
        prefix = "_rac_driver_test"
        presentation = ModuleType(f"{prefix}.presentation")
        self.state = SimpleNamespace(active_session=None, render_event=None)
        presentation.runtime_state = self.state
        runtime = ModuleType(f"{prefix}.blender.runtime")
        runtime.BlenderBatchSession = object
        runtime.BatchIntegrityError = type("BatchIntegrityError", (RuntimeError,), {})
        self.integrity_error = runtime.BatchIntegrityError
        self.bpy = SimpleNamespace(app=SimpleNamespace(is_job_running=Mock(return_value=False)))
        modules = {
            prefix: ModuleType(prefix),
            f"{prefix}.presentation": presentation,
            f"{prefix}.application": application,
            f"{prefix}.blender": ModuleType(f"{prefix}.blender"),
            f"{prefix}.blender.runtime": runtime,
            "bpy": self.bpy,
        }
        spec = importlib.util.spec_from_file_location(
            f"{prefix}.presentation.host_drivers",
            Path(__file__).parents[2] / "camera_batch_renderer/presentation/host_drivers.py",
        )
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(module)
        self.session = SimpleNamespace(
            coordinator=SimpleNamespace(current_action=object()),
            adapter=SimpleNamespace(has_fresh_output=Mock(return_value=False)),
            complete_current=Mock(),
            fail_current=Mock(),
            cancel=Mock(),
            fail=Mock(),
            record_diagnostic=Mock(),
        )
        self.state.active_session = self.session
        self.driver = module.AsyncTimerDriver(Mock(), self.session)
        self.driver._waiting = True
        self.driver._update_progress = Mock()
        self.driver._finish_poll = Mock(return_value=None)
        self.time = module.time

    def test_committed_output_manifest_failure_does_not_fail_next_action(self):
        self.session.adapter.has_fresh_output.return_value = True
        self.session.complete_current.side_effect = self.integrity_error("manifest full")
        self.driver._poll()
        self.session.fail_current.assert_not_called()
        self.session.fail.assert_called_once()
        self.driver._finish_poll.assert_called_once_with(cancelled=False)

    def test_stop_between_actions_does_not_start_an_extra_image(self):
        self.driver._waiting = False
        self.session.coordinator.snapshot = Mock(
            return_value=SimpleNamespace(cancel_requested=True))
        self.driver._poll()
        self.driver._finish_poll.assert_called_once_with(cancelled=True)
        self.session.fail_current.assert_not_called()

    def test_hours_of_active_cycles_never_times_out_or_commits_early(self):
        self.bpy.app.is_job_running.return_value = True
        self.state.render_event = application.RENDER_COMPLETE
        self.session.adapter.has_fresh_output.return_value = True
        with patch.object(self.time, "monotonic", return_value=36000):
            for _ in range(100):
                self.assertEqual(self.driver._poll(), 0.15)
        self.session.complete_current.assert_not_called()
        self.session.fail_current.assert_not_called()

    def test_lost_handler_uses_fresh_file_only_after_job_stops(self):
        self.session.adapter.has_fresh_output.return_value = True
        self.driver._poll()
        self.session.complete_current.assert_called_once()
        self.assertFalse(self.driver._waiting)

    def test_silent_idle_failure_is_recorded_instead_of_waiting_forever(self):
        with patch.object(self.time, "monotonic", side_effect=[1, 2, 4]):
            self.driver._poll()
            self.driver._poll()
            self.session.fail_current.assert_not_called()
            self.driver._poll()
        self.session.fail_current.assert_called_once()
        self.assertIn("without an output", self.session.fail_current.call_args.args[0])

    def test_native_cancel_waits_for_job_teardown(self):
        self.state.render_event = application.RENDER_CANCELLED
        self.bpy.app.is_job_running.return_value = True
        self.driver._poll()
        self.driver._finish_poll.assert_not_called()
        self.bpy.app.is_job_running.return_value = False
        self.driver._poll()
        self.driver._finish_poll.assert_called_once_with(cancelled=True)
        self.session.complete_current.assert_not_called()

    def prepare_finish(self):
        self.session.coordinator.request_cancel = Mock()
        self.session.coordinator.is_finished = True
        self.session.coordinator.snapshot = Mock(
            return_value=SimpleNamespace(status=BatchStatus.FAILED, error="Disk is read-only")
        )
        self.session.scene = SimpleNamespace(rac_settings=SimpleNamespace(status_text="Rendering"))
        self.session.finish = Mock()
        self.driver._remove_timer = Mock()
        self.state.clear = lambda: setattr(self.state, "active_session", None)

    def test_deferred_disable_only_requests_cancel_until_safe_finish(self):
        self.prepare_finish()
        callback = Mock(side_effect=lambda: self.assertIsNone(self.state.active_session))
        self.driver.defer_shutdown(callback)
        self.session.coordinator.request_cancel.assert_called_once()
        self.session.finish.assert_not_called()
        callback.assert_not_called()
        self.driver._finish(cancelled=False)
        self.session.finish.assert_called_once()
        self.driver._remove_timer.assert_called_once()
        callback.assert_called_once()
        self.assertEqual(self.session.scene.rac_settings.status_text, "Failed: Disk is read-only")

    def test_cleanup_error_still_removes_timer_and_finishes_deferred_disable(self):
        self.prepare_finish()
        self.session.finish.side_effect = OSError("Manifest write failed")
        callback = Mock(side_effect=lambda: self.assertIsNone(self.state.active_session))
        self.driver.defer_shutdown(callback)
        with self.assertRaisesRegex(OSError, "Manifest write failed"):
            self.driver._finish(cancelled=False)
        self.driver._remove_timer.assert_called_once()
        callback.assert_called_once()
