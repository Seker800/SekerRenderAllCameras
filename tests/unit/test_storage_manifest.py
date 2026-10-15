import ctypes
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from camera_batch_renderer.infrastructure.manifest import AtomicJsonWriter
from camera_batch_renderer.infrastructure.storage import (
    WORK_DIRECTORY_NAME,
    mark_complete,
    mark_incomplete,
    prepare_output_directory,
)


class StorageTests(unittest.TestCase):
    def test_persistent_sharing_lock_reports_failure_without_deleting_old_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            allocation = prepare_output_directory(root)
            final = root / "previous.png"
            final.write_bytes(b"keep")
            locked = OSError("sharing violation")
            locked.winerror = 32
            with (
                patch(
                    "camera_batch_renderer.infrastructure.storage.shutil.rmtree", side_effect=locked
                ) as remove,
                patch("camera_batch_renderer.infrastructure.storage.time.sleep"),
            ):
                with self.assertRaisesRegex(OSError, "file may still be in use"):
                    prepare_output_directory(root)
                self.assertEqual(remove.call_count, 4)
                with self.assertRaisesRegex(OSError, "file may still be in use"):
                    mark_complete(allocation)
            self.assertEqual(final.read_bytes(), b"keep")

    @unittest.skipUnless(os.name == "nt", "Windows file sharing regression")
    def test_start_recovers_a_short_file_lock_without_another_click(self):
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            allocation = prepare_output_directory(root)
            final = root / "previous.png"
            final.write_bytes(b"keep previous output")
            held = allocation.staging_directory / "held.tmp"
            held.write_bytes(b"previous temporary image")
            handle = kernel.CreateFileW(str(held), 0x80000000, 1, None, 3, 128, None)
            self.assertNotEqual(handle, wintypes.HANDLE(-1).value)
            release = threading.Timer(0.15, kernel.CloseHandle, args=(handle,))
            release.start()
            try:
                replacement = prepare_output_directory(root)
                self.assertTrue(replacement.marker.is_file())
                self.assertFalse(held.exists())
                self.assertEqual(final.read_bytes(), b"keep previous output")
            finally:
                release.join()

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
                attributes = ctypes.windll.kernel32.GetFileAttributesW(str(first.working_directory))
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
