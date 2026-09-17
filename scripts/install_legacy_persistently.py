from __future__ import annotations

import os
from pathlib import Path

import bpy


def main() -> None:
    package = Path(os.environ["RAC_LEGACY_PACKAGE"]).resolve()
    if not package.is_file():
        raise FileNotFoundError(package)
    bpy.ops.preferences.addon_install(filepath=str(package), overwrite=True)
    bpy.ops.preferences.addon_enable(module="camera_batch_renderer")
    bpy.ops.wm.save_userpref()
    print(f"LEGACY_PLUGIN_INSTALLED_AND_ENABLED {package.name}", flush=True)


if __name__ == "__main__":
    main()
