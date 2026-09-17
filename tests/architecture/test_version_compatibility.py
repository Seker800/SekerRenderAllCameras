from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

from camera_batch_renderer.version import VERSION, VERSION_TEXT

ROOT = Path(__file__).parents[2]
PACKAGE = ROOT / "camera_batch_renderer"


class VersionCompatibilityTests(unittest.TestCase):
    def test_version_is_consistent_across_package_surfaces(self) -> None:
        entry_point = (PACKAGE / "__init__.py").read_text(encoding="utf-8")
        manifest = (PACKAGE / "blender_manifest.toml").read_text(encoding="utf-8")
        runtime = (PACKAGE / "blender" / "runtime.py").read_text(encoding="utf-8")
        panel = (PACKAGE / "presentation" / "panel.py").read_text(encoding="utf-8")
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

        manifest_version = re.search(r'^version = "([^"]+)"$', manifest, re.MULTILINE)
        project_version = re.search(r'^version = "([^"]+)"$', project, re.MULTILINE)
        self.assertIsNotNone(manifest_version)
        self.assertIsNotNone(project_version)
        version = manifest_version.group(1)
        self.assertEqual(project_version.group(1), version)
        self.assertEqual(version, VERSION_TEXT)
        self.assertEqual(tuple(int(part) for part in version.split(".")), VERSION)
        self.assertIn(f'"version": {VERSION}', entry_point)
        self.assertIn('"addon_version": VERSION_TEXT', runtime)
        self.assertIn('text=f"Version {VERSION_TEXT} · Blender {TARGET_LABEL}"', panel)

    def test_legacy_bl_info_is_literal_for_blender_discovery(self) -> None:
        entry_point = (PACKAGE / "__init__.py").read_text(encoding="utf-8")
        tree = ast.parse(entry_point)
        assignment = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "bl_info"
                for target in node.targets
            )
        )
        info = ast.literal_eval(assignment.value)
        self.assertEqual(info["version"], VERSION)

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
