"""Fail closed before GUI tests load factory settings or register any add-on."""
from __future__ import annotations

import os
from pathlib import Path


def require_isolated_profile() -> None:
    real_profile = (Path(os.environ["APPDATA"]) / "Blender Foundation" / "Blender").resolve()
    for suffix in ("CONFIG", "SCRIPTS", "DATAFILES", "EXTENSIONS", "RESOURCES"):
        name = f"BLENDER_USER_{suffix}"
        value = os.environ.get(name)
        if not value:
            raise RuntimeError(f"{name} is required; run scripts/run_full_test_suite.ps1")
        path = Path(value).resolve()
        if not path.is_dir() or path == real_profile or real_profile in path.parents:
            raise RuntimeError(f"{name} must be an existing isolated directory")
