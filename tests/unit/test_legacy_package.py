from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_legacy_package import build_legacy_package


class LegacyPackageTests(unittest.TestCase):
    def test_build_is_deterministic_and_excludes_extension_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "camera_batch_renderer"
            source.mkdir()
            (source / "__init__.py").write_text("value = 1\n", encoding="utf-8")
            (source / "module.py").write_text("value = 2\n", encoding="utf-8")
            (source / "blender_manifest.toml").write_text("ignored", encoding="utf-8")
            cache = source / "__pycache__"
            cache.mkdir()
            (cache / "module.pyc").write_bytes(b"ignored")
            first = root / "first.zip"
            second = root / "second.zip"

            build_legacy_package(source, first)
            os.utime(source / "module.py", (2_000_000_000, 2_000_000_000))
            build_legacy_package(source, second)

            first_hash = hashlib.sha256(first.read_bytes()).digest()
            second_hash = hashlib.sha256(second.read_bytes()).digest()
            self.assertEqual(first_hash, second_hash)
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(
                    archive.namelist(),
                    [
                        "camera_batch_renderer/__init__.py",
                        "camera_batch_renderer/module.py",
                    ],
                )


if __name__ == "__main__":
    unittest.main()
