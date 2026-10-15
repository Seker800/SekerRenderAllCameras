from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.build_target_packages import build_all
from scripts.release_gate import (
    read_project_version,
    verify_feature_surface,
    verify_online_release,
    verify_package_parity,
    verify_target_packages,
)

ROOT = Path(__file__).resolve().parents[2]


def write_archive(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


class ReleaseGateTests(unittest.TestCase):
    def test_renamed_old_packages_are_rejected_against_current_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "camera_batch_renderer", root / "camera_batch_renderer")
            shutil.copytree(ROOT / "packaging", root / "packaging")
            shutil.copy2(ROOT / "pyproject.toml", root / "pyproject.toml")
            version = read_project_version(root)
            build_all(
                root / "packaging" / "blender_targets.json",
                root / "camera_batch_renderer",
                root / "staging",
                root / "dist",
            )
            verify_target_packages(root, version)
            for changed_file, old_content in (
                ("version.py", b"VERSION = (0, 1, 0)\nVERSION_TEXT = '0.1.0'\n"),
                ("application/coordinator.py", b"# old feature implementation\n"),
            ):
                with self.subTest(changed_file=changed_file):
                    build_all(
                        root / "packaging" / "blender_targets.json",
                        root / "camera_batch_renderer",
                        root / "staging",
                        root / "dist",
                    )
                    for archive_path in (root / "dist").glob("*.zip"):
                        with zipfile.ZipFile(archive_path) as archive:
                            entries = {name: archive.read(name) for name in archive.namelist()}
                        entry = next(name for name in entries if name.endswith(changed_file))
                        entries[entry] = old_content
                        write_archive(archive_path, entries)
                    with self.assertRaisesRegex(ValueError, "Package differs from current source"):
                        verify_target_packages(root, version)

    def test_source_version_surfaces_must_agree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "camera_batch_renderer").mkdir()
            (root / "camera_batch_renderer" / "version.py").write_text("VERSION = (1, 2, 3)\n")
            (root / "camera_batch_renderer" / "blender_manifest.toml").write_text(
                'version = "1.2.2"\n'
            )
            (root / "pyproject.toml").write_text('version = "1.2.3"\n')
            with self.assertRaisesRegex(ValueError, "Source version differs"):
                read_project_version(root)

    def test_accepts_identical_function_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            extension = root / "extension.zip"
            legacy = root / "legacy.zip"
            write_archive(
                extension,
                {"blender_manifest.toml": b"manifest", "module.py": b"same"},
            )
            write_archive(
                legacy,
                {"camera_batch_renderer/module.py": b"same"},
            )
            verify_package_parity(extension, legacy)

    def test_rejects_different_function_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            extension = root / "extension.zip"
            legacy = root / "legacy.zip"
            write_archive(
                extension,
                {"blender_manifest.toml": b"manifest", "module.py": b"new"},
            )
            write_archive(
                legacy,
                {"camera_batch_renderer/module.py": b"old"},
            )
            with self.assertRaisesRegex(ValueError, "Package contents differ"):
                verify_package_parity(extension, legacy)

    def test_online_release_must_match_local_artifact_hash(self) -> None:
        class Response:
            status = 200

            def __init__(self, payload: bytes) -> None:
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self, _size: int = -1) -> bytes:
                payload, self.payload = self.payload, b""
                return payload

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "packaging").mkdir()
            (root / "dist").mkdir()
            config = {
                "targets": [
                    {
                        "id": "blender-test",
                        "package_type": "extension",
                    }
                ]
            }
            (root / "packaging" / "blender_targets.json").write_text(
                json.dumps(config), encoding="utf-8"
            )
            (root / "packaging" / "release_contract.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "module_id": "camera_batch_renderer",
                        "asset_stem": "RenderAllCameras",
                        "output_options": {
                            "include_beauty": {},
                            "include_alpha": {},
                            "include_object_id": {},
                            "include_material_id": {},
                        },
                    }
                ),
                encoding="utf-8",
            )
            artifact = root / "dist" / "RenderAllCameras-1.2.3-blender-test.zip"
            artifact.write_bytes(b"tested payload")
            (root / "README.md").write_text("verified README", encoding="utf-8")
            release = {
                "tag_name": "v1.2.3",
                "name": "Release v1.2.3",
                "draft": False,
                "prerelease": False,
                "assets": [{"name": artifact.name}],
                "body": "1.2.3 " + artifact.name + " 1.2.3 "
                + hashlib.sha256(artifact.read_bytes()).hexdigest(),
            }
            config["targets"][0]["tested_version"] = "1.2.3"
            (root / "packaging" / "blender_targets.json").write_text(
                json.dumps(config), encoding="utf-8"
            )

            def online_response(request, timeout):
                if "api.github.com" in request.full_url:
                    return Response(json.dumps(release).encode())
                if "raw.githubusercontent.com" in request.full_url:
                    return Response(b"verified README")
                return Response(b"tested payload")

            with patch(
                "scripts.release_gate.urllib.request.urlopen",
                side_effect=online_response,
            ):
                verify_online_release(root, "1.2.3")

            release["body"] = "1.2.3 " + artifact.name
            with patch(
                "scripts.release_gate.urllib.request.urlopen",
                side_effect=online_response,
            ):
                with self.assertRaisesRegex(ValueError, "Release notes omit"):
                    verify_online_release(root, "1.2.3")
            release["body"] += " " + hashlib.sha256(artifact.read_bytes()).hexdigest()

            def stale_readme_response(request, timeout):
                if "api.github.com" in request.full_url:
                    return Response(json.dumps(release).encode())
                return Response(b"old README")

            with patch(
                "scripts.release_gate.urllib.request.urlopen",
                side_effect=stale_readme_response,
            ):
                with self.assertRaisesRegex(ValueError, "main README differs"):
                    verify_online_release(root, "1.2.3")

            release["tag_name"] = "v1.2.2"
            with patch(
                "scripts.release_gate.urllib.request.urlopen",
                side_effect=online_response,
            ):
                with self.assertRaisesRegex(ValueError, "tag or assets differ"):
                    verify_online_release(root, "1.2.3")
            release["tag_name"] = "v1.2.3"

            def changed_response(request, timeout):
                if "api.github.com" in request.full_url:
                    return Response(json.dumps(release).encode())
                if "raw.githubusercontent.com" in request.full_url:
                    return Response(b"verified README")
                return Response(b"different payload")

            with patch(
                "scripts.release_gate.urllib.request.urlopen",
                side_effect=changed_response,
            ):
                with self.assertRaisesRegex(ValueError, "hash does not match"):
                    verify_online_release(root, "1.2.3")

    def test_feature_surface_rejects_missing_ui_option(self) -> None:
        contract = {
            "output_options": {"include_beauty": {"label": "Render Beauty", "default": True}}
        }
        payload = {
            "presentation/properties.py": (
                b'include_beauty: bpy.props.BoolProperty(name="Render Beauty", default=True)'
            ),
            "presentation/panel.py": b"",
        }
        with self.assertRaisesRegex(ValueError, "does not draw"):
            verify_feature_surface(payload, contract)
        payload["presentation/panel.py"] = b'row.prop(settings, "include_beauty")'
        verify_feature_surface(payload, contract)


if __name__ == "__main__":
    unittest.main()
