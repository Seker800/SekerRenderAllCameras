from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_target_packages import build_all

ROOT = Path(__file__).parents[2]


class TargetPackagingTests(unittest.TestCase):
    def test_builds_one_version_bounded_package_per_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            results = build_all(
                ROOT / "packaging" / "blender_targets.json",
                ROOT / "camera_batch_renderer",
                temporary / "staging",
                temporary / "dist",
            )

            self.assertEqual(len(results), 5)
            self.assertEqual(len({item["artifact"] for item in results}), 5)
            for item in results:
                artifact = Path(item["artifact"])
                self.assertTrue(artifact.is_file())
                with zipfile.ZipFile(artifact) as archive:
                    names = set(archive.namelist())
                    prefix = "camera_batch_renderer/" if item["package_type"] == "legacy" else ""
                    policy = archive.read(
                        f"{prefix}presentation/host_policy.py"
                    ).decode("utf-8")
                    self.assertIn(f'TARGET_ID = {item["id"]!r}', policy)
                    self.assertIn(item["driver"], policy)
                    manifest_name = f"{prefix}blender_manifest.toml"
                    if item["package_type"] == "legacy":
                        self.assertNotIn(manifest_name, names)
                    else:
                        manifest = archive.read(manifest_name).decode("utf-8")
                        self.assertIn(
                            f'blender_version_min = "{item["version_min"]}"', manifest
                        )
                        self.assertIn(
                            f'blender_version_max = "{item["version_max"]}"', manifest
                        )

    def test_target_configuration_has_unique_ids_and_tested_versions(self) -> None:
        payload = json.loads(
            (ROOT / "packaging" / "blender_targets.json").read_text(encoding="utf-8")
        )
        targets = payload["targets"]
        self.assertEqual(len({item["id"] for item in targets}), len(targets))
        self.assertEqual(len({item["tested_version"] for item in targets}), len(targets))


if __name__ == "__main__":
    unittest.main()
