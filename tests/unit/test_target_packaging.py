from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from camera_batch_renderer.version import VERSION_TEXT
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
            contract = json.loads(
                (ROOT / "packaging" / "release_contract.json").read_text(encoding="utf-8")
            )
            for item in results:
                artifact = Path(item["artifact"])
                self.assertTrue(artifact.is_file())
                self.assertEqual(
                    artifact.name,
                    f"{contract['asset_stem']}-{VERSION_TEXT}-{item['id']}.zip",
                )
                with zipfile.ZipFile(artifact) as archive:
                    names = set(archive.namelist())
                    prefix = "camera_batch_renderer/" if item["package_type"] == "legacy" else ""
                    policy = archive.read(f"{prefix}presentation/host_policy.py").decode("utf-8")
                    entry = archive.read(f"{prefix}__init__.py").decode("utf-8")
                    minimum = tuple(int(part) for part in item["version_min"].split("."))
                    maximum = tuple(int(part) for part in item["version_max"].split("."))
                    self.assertIn(f"TARGET_ID = {item['id']!r}", policy)
                    blender_label = item["id"].removeprefix("blender-").replace("-lts", " LTS")
                    display_name = (
                        f"{contract['display_name']} {VERSION_TEXT} (Blender {blender_label})"
                    )
                    self.assertIn(f"TARGET_LABEL = {blender_label!r}", policy)
                    self.assertIn(f'"name": "{display_name}"', entry)
                    self.assertIn(item["driver"], policy)
                    self.assertIn(
                        f"SUPPORTED_VERSION_MIN = {minimum!r}",
                        policy,
                    )
                    self.assertIn(
                        f"SUPPORTED_VERSION_MAX = {maximum!r}",
                        policy,
                    )
                    self.assertIn(
                        f'"blender": {minimum!r}',
                        entry,
                    )
                    manifest_name = f"{prefix}blender_manifest.toml"
                    if item["package_type"] == "legacy":
                        self.assertNotIn(manifest_name, names)
                    else:
                        manifest = archive.read(manifest_name).decode("utf-8")
                        self.assertIn(f'name = "{display_name}"', manifest)
                        self.assertIn(f'blender_version_min = "{item["version_min"]}"', manifest)
                        self.assertIn(f'blender_version_max = "{item["version_max"]}"', manifest)

    def test_target_configuration_has_unique_ids_and_tested_versions(self) -> None:
        payload = json.loads(
            (ROOT / "packaging" / "blender_targets.json").read_text(encoding="utf-8")
        )
        targets = payload["targets"]
        self.assertEqual(len({item["id"] for item in targets}), len(targets))
        self.assertEqual(len({item["tested_version"] for item in targets}), len(targets))


if __name__ == "__main__":
    unittest.main()
