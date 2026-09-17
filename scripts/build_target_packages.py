from __future__ import annotations

import json
import os
import re
import sys
import zipfile
from pathlib import Path

try:
    from scripts.build_legacy_package import build_legacy_package
    from scripts.prepare_target_source import load_target, prepare
except ModuleNotFoundError:  # Direct execution adds scripts/, not the repository, to sys.path.
    from build_legacy_package import build_legacy_package
    from prepare_target_source import load_target, prepare

ARCHIVE_TIMESTAMP = (2000, 1, 1, 0, 0, 0)
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def included_files(source: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in source.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix.lower() not in EXCLUDED_SUFFIXES
        ),
        key=lambda path: path.relative_to(source).as_posix(),
    )


def build_extension_package(source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            for path in included_files(source):
                relative = path.relative_to(source).as_posix()
                info = zipfile.ZipInfo(relative, ARCHIVE_TIMESTAMP)
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()


def package_version(source: Path) -> str:
    manifest = (source / "blender_manifest.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', manifest, re.MULTILINE)
    if match is None:
        raise ValueError("Cannot read package version from blender_manifest.toml")
    return match.group(1)


def build_all(config: Path, source: Path, staging: Path, output: Path) -> list[dict[str, str]]:
    payload = json.loads(config.read_text(encoding="utf-8"))
    contract = json.loads((config.parent / "release_contract.json").read_text(encoding="utf-8"))
    if source.name != contract["module_id"]:
        raise ValueError("Source package does not match the release contract module_id")
    version = package_version(source)
    results = []
    for target_value in payload["targets"]:
        target = load_target(config, target_value["id"])
        staged_source = staging / target["id"] / source.name
        prepare(source, staged_source, target)
        artifact = output / f"{contract['asset_stem']}-{version}-{target['id']}.zip"
        if target["package_type"] == "legacy":
            build_legacy_package(staged_source, artifact)
        else:
            build_extension_package(staged_source, artifact)
        results.append(
            {
                **target,
                "source": str(staged_source.resolve()),
                "artifact": str(artifact.resolve()),
            }
        )
    return results


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit("usage: build_target_packages.py CONFIG SOURCE STAGING OUTPUT")
    config, source, staging, output = (Path(value) for value in sys.argv[1:])
    results = build_all(config, source, staging, output)
    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
