import ctypes
import json
import os
import tempfile
import unittest
from pathlib import Path

from camera_batch_renderer.infrastructure.manifest import AtomicJsonWriter
from camera_batch_renderer.infrastructure.storage import (
    WORK_DIRECTORY_NAME,
    mark_complete,
    mark_incomplete,
    prepare_output_directory,
)


class StorageTests(unittest.TestCase):
    def test_fixed_output_directory_preserves_existing_files_and_updates_markers(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "SekerRenderAllCameras"
            output.mkdir()
            existing = output / "old.png"
            existing.write_bytes(b"old")
            first = prepare_output_directory(output)
            second = prepare_output_directory(output)
            self.assertEqual(first.directory, second.directory)
            self.assertEqual(existing.read_bytes(), b"old")
            self.assertTrue(first.marker.exists())
            self.assertEqual(first.working_directory, output / WORK_DIRECTORY_NAME)
            self.assertEqual(first.staging_directory, first.working_directory / "staging")
            self.assertEqual(
                {item.name for item in output.iterdir()},
                {"old.png", WORK_DIRECTORY_NAME},
            )
            if os.name == "nt":
                attributes = ctypes.windll.kernel32.GetFileAttributesW(
                    str(first.working_directory)
                )
                self.assertNotEqual(attributes, -1)
                self.assertTrue(attributes & 0x2)
            incomplete = mark_incomplete(first)
            self.assertTrue(incomplete.exists())
            mark_complete(first)
            self.assertFalse(incomplete.exists())
            self.assertFalse(first.working_directory.exists())

    def test_atomic_json_is_utf8_and_leaves_no_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            writer = AtomicJsonWriter(path)
            writer.write({"schema_version": 1, "name": "客厅"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["name"], "客厅")
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_atomic_json_can_keep_temporary_file_in_work_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "manifest.json"
            working = root / WORK_DIRECTORY_NAME
            AtomicJsonWriter(path, temporary_directory=working).write({"status": "ok"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["status"], "ok")
            self.assertEqual(list(root.glob("*.tmp")), [])
            self.assertEqual(list(working.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
