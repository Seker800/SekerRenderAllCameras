from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

import bpy


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


package_path = Path(os.environ["RAC_LEGACY_PACKAGE"]).resolve()
expected_minimum = tuple(int(part) for part in os.environ["RAC_EXPECTED_VERSION_MIN"].split("."))
expected_target = os.environ["RAC_EXPECTED_TARGET"]
assert_true(package_path.is_file(), f"Legacy package is missing: {package_path}")
assert_true(
    "camera_batch_renderer" not in sys.modules,
    "Legacy package was already loaded before the isolated install",
)

installed_directory: Path | None = None
enabled = False
try:
    bpy.ops.preferences.addon_install(filepath=str(package_path), overwrite=True)
    bpy.ops.preferences.addon_enable(module="camera_batch_renderer")
    enabled = True

    import camera_batch_renderer  # noqa: E402
    from camera_batch_renderer.presentation.host_policy import TARGET_ID  # noqa: E402
    from camera_batch_renderer.presentation.panel import (  # noqa: E402
        RAC_PT_panel,
        RAC_PT_view3d_panel,
    )

    installed_directory = Path(camera_batch_renderer.__file__).resolve().parent
    assert_true(
        camera_batch_renderer.bl_info["blender"] == expected_minimum,
        "Minimum version is wrong",
    )
    assert_true(
        installed_directory.is_relative_to(
            Path(os.environ["BLENDER_USER_SCRIPTS"]).resolve()
        ),
        "Legacy acceptance imported a package outside the isolated install root",
    )
    assert_true(TARGET_ID == expected_target, "Installed target policy is wrong")
    assert_true(hasattr(bpy.types.Scene, "rac_settings"), "Scene settings were not registered")
    assert_true(RAC_PT_panel.is_registered, "Output Properties panel was not registered")
    assert_true(RAC_PT_view3d_panel.is_registered, "3D Viewport N-panel was not registered")

    os.environ["RAC_INSTALLED_MODULE"] = "camera_batch_renderer"
    acceptance_path = Path(__file__).with_name("run_installed_demo.py")
    spec = importlib.util.spec_from_file_location(
        "rac_installed_demo_acceptance", acceptance_path
    )
    assert_true(
        spec is not None and spec.loader is not None,
        "Cannot load installed demo acceptance",
    )
    acceptance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(acceptance)
    acceptance.main()
finally:
    if enabled:
        bpy.ops.preferences.addon_disable(module="camera_batch_renderer")
    if installed_directory is not None and installed_directory.exists():
        # Blender 4.0's removal operator dereferences context.area in background mode.
        # Removing the already-disabled, exact installed directory is its headless equivalent.
        shutil.rmtree(installed_directory)

assert_true(not hasattr(bpy.types.Scene, "rac_settings"), "Scene settings leaked after disable")
assert_true(
    installed_directory is not None and not installed_directory.exists(),
    "Installed add-on directory was not removed",
)
print("LEGACY_INSTALL_TEST_OK")
