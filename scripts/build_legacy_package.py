from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

ARCHIVE_TIMESTAMP = (2000, 1, 1, 0, 0, 0)
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def included_files(source: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in source.rglob("*")
            if path.is_file()
            and path.name != "blender_manifest.toml"
            and "__pycache__" not in path.parts
            and path.suffix.lower() not in EXCLUDED_SUFFIXES
        ),
        key=lambda path: path.relative_to(source).as_posix(),
    )


def build_legacy_package(source: Path, output: Path) -> None:
    source = source.resolve()
    output = output.resolve()
    if not (source / "__init__.py").is_file():
        raise ValueError(f"Legacy add-on entry point is missing: {source / '__init__.py'}")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            for path in included_files(source):
                relative = path.relative_to(source).as_posix()
                info = zipfile.ZipInfo(f"{source.name}/{relative}", ARCHIVE_TIMESTAMP)
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: build_legacy_package.py SOURCE OUTPUT")
    build_legacy_package(Path(sys.argv[1]), Path(sys.argv[2]))
