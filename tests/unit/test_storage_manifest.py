import json
import tempfile
import unittest
from pathlib import Path

from camera_batch_renderer.infrastructure.manifest import AtomicJsonWriter
from camera_batch_renderer.infrastructure.storage import (
    allocate_batch,
    mark_complete,
    mark_incomplete,
)


class StorageTests(unittest.TestCase):
    def test_batch_allocation_and_markers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = allocate_batch(root)
            second = allocate_batch(root)
            self.assertEqual((first.label, second.label), ("001", "002"))
            self.assertTrue(first.marker.exists())
            incomplete = mark_incomplete(first)
            self.assertTrue(incomplete.exists())
            mark_complete(first)
            self.assertFalse(incomplete.exists())

    def test_atomic_json_is_utf8_and_leaves_no_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            writer = AtomicJsonWriter(path)
            writer.write({"schema_version": 1, "name": "客厅"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["name"], "客厅")
            self.assertEqual(list(path.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
