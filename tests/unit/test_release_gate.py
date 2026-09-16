from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.release_gate import verify_package_parity


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


if __name__ == "__main__":
    unittest.main()
