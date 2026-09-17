import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestEnvironmentSafetyTests(unittest.TestCase):
    def test_install_lifecycle_creates_every_blender_override_before_install(self):
        script = (ROOT / "scripts" / "run_full_test_suite.ps1").read_text(encoding="utf-8")
        assignments = script.index(
            '$env:BLENDER_USER_CONFIG = Join-Path $testRoot "config"',
            script.index('$testRoot = Join-Path $reportRoot "install-'),
        )
        initialization = script.index("$isolationDirectories = @(", assignments)
        creation = script.index(
            "New-Item -ItemType Directory -Force -Path $directory", initialization
        )
        extension_install = script.index('"--command", "extension", "install-file"', creation)
        self.assertLess(assignments, initialization)
        self.assertLess(initialization, creation)
        self.assertLess(creation, extension_install)
        for variable in (
            "$env:BLENDER_USER_CONFIG",
            "$env:BLENDER_USER_SCRIPTS",
            "$env:BLENDER_USER_DATAFILES",
            "$env:BLENDER_USER_EXTENSIONS",
            "$env:BLENDER_USER_RESOURCES",
        ):
            self.assertIn(variable, script[initialization:creation])


if __name__ == "__main__":
    unittest.main()
