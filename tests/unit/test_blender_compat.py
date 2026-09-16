from __future__ import annotations

import unittest
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace

ROOT = Path(__file__).parents[2]
is_editable_id = run_path(
    str(ROOT / "camera_batch_renderer" / "blender" / "compat.py")
)["is_editable_id"]


class BlenderIdCompatibilityTests(unittest.TestCase):
    def test_uses_is_editable_when_blender_exposes_it(self) -> None:
        self.assertTrue(
            is_editable_id(
                SimpleNamespace(is_editable=True, library=object(), override_library=None)
            )
        )
        self.assertFalse(
            is_editable_id(
                SimpleNamespace(is_editable=False, library=None, override_library=object())
            )
        )

    def test_blender_4_0_treats_local_ids_as_editable(self) -> None:
        data_block = SimpleNamespace(library=None, override_library=None)

        self.assertTrue(is_editable_id(data_block))

    def test_blender_4_0_rejects_directly_linked_ids(self) -> None:
        data_block = SimpleNamespace(library=object(), override_library=None)

        self.assertFalse(is_editable_id(data_block))

    def test_blender_4_0_accepts_library_overrides(self) -> None:
        data_block = SimpleNamespace(library=object(), override_library=object())

        self.assertTrue(is_editable_id(data_block))


if __name__ == "__main__":
    unittest.main()
