from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from camera_batch_renderer.infrastructure.diagnostics import DiagnosticJournal


class DiagnosticTests(unittest.TestCase):
    def test_separate_attempts_preserve_failed_report(self):
        with tempfile.TemporaryDirectory() as directory:
            first = DiagnosticJournal(Path(directory), {"engine": "CYCLES"})
            first.record("start_failed", error="access denied", traceback="trace")
            second = DiagnosticJournal(Path(directory), {})
            second.record("click_received")
            self.assertNotEqual(first.path, second.path)
            data = json.loads(first.path.read_text())
            self.assertEqual(data["errors"][0]["error"], "access denied")
            self.assertEqual(data["environment"]["engine"], "CYCLES")

    def test_heartbeat_throttles_and_history_is_bounded_without_losing_error(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = DiagnosticJournal(Path(directory), {})
            with patch("camera_batch_renderer.infrastructure.diagnostics.time.monotonic",
                       return_value=10):
                journal.record("image_failed", error="GPU failed")
                for _ in range(20):
                    journal.record("rendering", heartbeat=True)
            self.assertEqual(len(journal.payload["events"]), 1)
            for index in range(150):
                journal.record("preparing", index=index)
            data = json.loads(journal.path.read_text())
            self.assertEqual(len(data["events"]), 128)
            self.assertEqual(data["errors"][0]["error"], "GPU failed")

    def test_replace_failure_preserves_last_readable_report_and_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = DiagnosticJournal(Path(directory), {})
            journal.record("render_submitted")
            before = journal.path.read_bytes()
            with patch("camera_batch_renderer.infrastructure.manifest.os.replace",
                       side_effect=PermissionError("locked")):
                self.assertFalse(journal.record("image_failed", error="missing output"))
            self.assertEqual(journal.path.read_bytes(), before)
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])
            self.assertTrue(journal.write_error)
            self.assertTrue(journal.record("finished"))
            self.assertEqual(journal.write_error, "")
            self.assertEqual(json.loads(journal.path.read_text())["errors"][0]["error"],
                             "missing output")

    def test_checkpoint_survives_abrupt_process_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            code = (
                "import os,sys; from pathlib import Path; "
                "from camera_batch_renderer.infrastructure.diagnostics import DiagnosticJournal; "
                "j=DiagnosticJournal(Path(sys.argv[1]),{'engine':'CYCLES'}); "
                "j.record('rendering',camera='Camera 1',channel='Beauty'); os._exit(23)"
            )
            result = subprocess.run([sys.executable, "-c", code, directory], check=False)
            self.assertEqual(result.returncode, 23)
            report = next(Path(directory).glob("Render-*.json"))
            data = json.loads(report.read_text())
            self.assertEqual(data["last_checkpoint"]["event"], "rendering")
            self.assertEqual(data["last_checkpoint"]["camera"], "Camera 1")
