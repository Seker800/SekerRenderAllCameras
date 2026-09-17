from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path


def version_tuple(value: str) -> tuple[int, int, int]:
    parts = tuple(int(part) for part in value.split("."))
    if len(parts) != 3:
        raise ValueError(f"Expected three-part Blender version, got {value!r}")
    return parts


def load_target(config_path: Path, target_id: str) -> dict[str, str]:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    matches = [item for item in payload["targets"] if item["id"] == target_id]
    if len(matches) != 1:
        raise ValueError(f"Unknown or duplicate Blender target: {target_id}")
    return matches[0]


def policy_source(target: dict[str, str]) -> str:
    minimum = version_tuple(target["version_min"])
    maximum = version_tuple(target["version_max"])
    start_result = "{'RUNNING_MODAL'}" if target["driver"] == "ModalEventDriver" else "{'FINISHED'}"
    return f'''"""Generated host policy for {target["id"]}; do not edit the staged copy."""

from __future__ import annotations

from .host_drivers import {target["driver"]}

TARGET_ID = {target["id"]!r}
TARGET_LABEL = {target["id"].removeprefix("blender-").replace("-lts", " LTS")!r}
SUPPORTED_VERSION_MIN = {minimum!r}
SUPPORTED_VERSION_MAX = {maximum!r}
HOST_DRIVER_CLASS = {target["driver"]}
OPERATOR_START_RESULT = {start_result}


def ensure_supported_version() -> None:
    import bpy  # noqa: PLC0415

    version = tuple(bpy.app.version[:3])
    if version < SUPPORTED_VERSION_MIN or version >= SUPPORTED_VERSION_MAX:
        raise RuntimeError(
            f"Package {{TARGET_ID}} supports Blender {{SUPPORTED_VERSION_MIN}} to "
            f"{{SUPPORTED_VERSION_MAX}}, but Blender {{version}} is running"
        )
'''


def prepare(source: Path, destination: Path, target: dict[str, str]) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    (destination / "presentation" / "host_policy.py").write_text(
        policy_source(target), encoding="utf-8", newline="\n"
    )

    version_match = re.search(
        r'^version = "([^"]+)"$',
        (source / "blender_manifest.toml").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if version_match is None:
        raise ValueError("Cannot read add-on version from blender_manifest.toml")
    blender_label = target["id"].removeprefix("blender-").replace("-lts", " LTS")
    display_name = f"Render All Cameras {version_match.group(1)} (Blender {blender_label})"

    entry_path = destination / "__init__.py"
    entry = entry_path.read_text(encoding="utf-8")
    minimum = version_tuple(target["version_min"])
    entry = re.sub(
        r'"blender": \(\d+, \d+, \d+\)',
        f'"blender": {minimum!r}',
        entry,
        count=1,
    )
    entry = entry.replace('"name": "Render All Cameras"', f'"name": "{display_name}"', 1)
    entry_path.write_text(entry, encoding="utf-8", newline="\n")

    manifest_path = destination / "blender_manifest.toml"
    if target["package_type"] == "extension":
        manifest = manifest_path.read_text(encoding="utf-8")
        manifest = manifest.replace('name = "Render All Cameras"', f'name = "{display_name}"', 1)
        manifest = re.sub(
            r'^blender_version_min = "[^"]+"$',
            f'blender_version_min = "{target["version_min"]}"',
            manifest,
            flags=re.MULTILINE,
        )
        if "blender_version_max" in manifest:
            manifest = re.sub(
                r'^blender_version_max = "[^"]+"$',
                f'blender_version_max = "{target["version_max"]}"',
                manifest,
                flags=re.MULTILINE,
            )
        else:
            manifest = manifest.replace(
                f'blender_version_min = "{target["version_min"]}"',
                f'blender_version_min = "{target["version_min"]}"\n'
                f'blender_version_max = "{target["version_max"]}"',
            )
        manifest_path.write_text(manifest, encoding="utf-8", newline="\n")


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit(
            "usage: prepare_target_source.py CONFIG SOURCE DESTINATION TARGET_ID"
        )
    config, source, destination, target_id = sys.argv[1:]
    target = load_target(Path(config), target_id)
    prepare(Path(source), Path(destination), target)
    print(json.dumps(target, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
