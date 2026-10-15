from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from runpy import run_path
from unittest.mock import patch

require_isolated_profile = run_path(
    str(Path(__file__).parents[2] / "scripts/blender_test_safety.py")
)["require_isolated_profile"]


class TestProfileSafety(unittest.TestCase):
    def test_missing_overrides_fail_closed(self):
        with patch.dict(os.environ, {"APPDATA": "/fake-profile"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "BLENDER_USER_CONFIG is required"):
                require_isolated_profile()

    def test_real_user_profile_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            profile = Path(root) / "Blender Foundation/Blender/4.0/config"
            profile.mkdir(parents=True)
            with patch.dict(os.environ, {"APPDATA": root, "BLENDER_USER_CONFIG": str(profile)}):
                with self.assertRaisesRegex(RuntimeError, "isolated directory"):
                    require_isolated_profile()

    def test_all_overrides_must_exist_before_starting(self):
        with tempfile.TemporaryDirectory() as root:
            env = {"APPDATA": str(Path(root) / "real")}
            for suffix in ("CONFIG", "SCRIPTS", "DATAFILES", "EXTENSIONS", "RESOURCES"):
                directory = Path(root) / "tests" / suffix
                directory.mkdir(parents=True)
                env[f"BLENDER_USER_{suffix}"] = str(directory)
            with patch.dict(os.environ, env):
                require_isolated_profile()
                Path(env["BLENDER_USER_SCRIPTS"]).rmdir()
                with self.assertRaisesRegex(RuntimeError, "BLENDER_USER_SCRIPTS"):
                    require_isolated_profile()
