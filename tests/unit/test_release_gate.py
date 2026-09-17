from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.release_gate import (
    verify_feature_surface,
    verify_online_release,
    verify_package_parity,
)


def write_archive(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


class ReleaseGateTests(unittest.TestCase):
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
            release = {
                "tag_name": "v1.2.3",
                "draft": False,
                "prerelease": False,
                "assets": [{"name": artifact.name}],
            }

            def online_response(request, timeout):
                if "api.github.com" in request.full_url:
                    return Response(json.dumps(release).encode())
                return Response(b"tested payload")

            with patch(
                "scripts.release_gate.urllib.request.urlopen",
                side_effect=online_response,
            ):
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
