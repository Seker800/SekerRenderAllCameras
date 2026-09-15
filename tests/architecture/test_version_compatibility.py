from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).parents[2]
PACKAGE = ROOT / "camera_batch_renderer"


class VersionCompatibilityTests(unittest.TestCase):
    def test_package_contract_covers_blender_4_0_2_and_later(self) -> None:
        entry_point = (PACKAGE / "__init__.py").read_text(encoding="utf-8")
        manifest = (PACKAGE / "blender_manifest.toml").read_text(encoding="utf-8")
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn('"blender": (4, 0, 2)', entry_point)
        self.assertIn('blender_version_min = "4.2.0"', manifest)
        self.assertNotIn("blender_version_max", manifest)
        self.assertIn('requires-python = ">=3.10"', project)
        self.assertIn('target-version = "py310"', project)

    def test_python_3_11_only_imports_stay_behind_compatibility_boundary(self) -> None:
        for path in PACKAGE.rglob("*.py"):
            if path.name == "compat.py":
                continue
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("from enum import StrEnum", source, str(path))
            self.assertNotIn("from datetime import UTC", source, str(path))


if __name__ == "__main__":
    unittest.main()
