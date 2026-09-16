from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.release_gate import verify_online_release, verify_package_parity


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

            def read(self, _size: int) -> bytes:
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
            artifact = root / "dist" / "camera_batch_renderer-1.2.3-blender-test.zip"
            artifact.write_bytes(b"tested payload")

            with patch(
                "scripts.release_gate.urllib.request.urlopen",
                return_value=Response(b"tested payload"),
            ):
                verify_online_release(root, "1.2.3")

            with patch(
                "scripts.release_gate.urllib.request.urlopen",
                return_value=Response(b"different payload"),
            ):
                with self.assertRaisesRegex(ValueError, "hash does not match"):
                    verify_online_release(root, "1.2.3")


if __name__ == "__main__":
    unittest.main()
