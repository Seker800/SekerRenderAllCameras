from __future__ import annotations

# ruff: noqa: I001

import os
import sys
from pathlib import Path

import bpy


package_parent = Path(os.environ["RAC_PACKAGE_PARENT"])
sys.path.insert(0, str(package_parent))

import camera_batch_renderer  # noqa: E402


expected_target = os.environ["RAC_EXPECTED_REJECTED_TARGET"]
try:
    camera_batch_renderer.register()
except RuntimeError as exc:
    message = str(exc)
    if expected_target not in message or str(tuple(bpy.app.version[:3])) not in message:
        raise AssertionError(f"Version rejection is unclear: {message}") from exc
else:
    camera_batch_renderer.unregister()
    raise AssertionError(
        f"Incompatible package {expected_target} accepted Blender {bpy.app.version_string}"
    )

print("TARGET_VERSION_REJECTION_OK")
