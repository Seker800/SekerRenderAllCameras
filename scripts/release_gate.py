from __future__ import annotations

import argparse
import re
import urllib.request
import zipfile
from pathlib import Path

PACKAGE_NAME = "camera_batch_renderer"
GITHUB_REPOSITORY = "Seker800/SekerRenderAllCameras"


def read_project_version(root: Path) -> str:
    source = (root / PACKAGE_NAME / "version.py").read_text(encoding="utf-8")
    match = re.search(r"^VERSION = \(([^)]+)\)$", source, re.MULTILINE)
    if match is None:
        raise ValueError("Cannot read VERSION from camera_batch_renderer/version.py")
    parts = tuple(int(part.strip()) for part in match.group(1).split(",") if part.strip())
    return ".".join(str(part) for part in parts)


def archive_payload(path: Path, *, legacy: bool) -> dict[str, bytes]:
    prefix = f"{PACKAGE_NAME}/"
    with zipfile.ZipFile(path) as archive:
        payload = {}
        for name in archive.namelist():
            if name.endswith("/"):
                continue
            normalized = name
            if legacy:
                if not name.startswith(prefix):
                    raise ValueError(f"Legacy archive has an invalid root entry: {name}")
                normalized = name[len(prefix) :]
            payload[normalized] = archive.read(name)
    return payload


def verify_package_parity(extension: Path, legacy: Path) -> None:
    extension_payload = archive_payload(extension, legacy=False)
    legacy_payload = archive_payload(legacy, legacy=True)
    manifest = extension_payload.pop("blender_manifest.toml", None)
    if manifest is None:
        raise ValueError("Extension archive is missing blender_manifest.toml")
    if "blender_manifest.toml" in legacy_payload:
        raise ValueError("Legacy archive must not contain blender_manifest.toml")
    extension_names = set(extension_payload)
    legacy_names = set(legacy_payload)
    if extension_names != legacy_names:
        missing = sorted(extension_names - legacy_names)
        extra = sorted(legacy_names - extension_names)
        raise ValueError(
            f"Package file sets differ; missing from Legacy={missing}, extra in Legacy={extra}"
        )
    different = sorted(
        name
        for name in extension_names
        if extension_payload[name] != legacy_payload[name]
    )
    if different:
        raise ValueError(f"Package contents differ: {different}")


def release_urls(version: str) -> tuple[str, str]:
    base = f"https://github.com/{GITHUB_REPOSITORY}/releases/latest/download"
    return (
        f"{base}/{PACKAGE_NAME}-{version}.zip",
        f"{base}/{PACKAGE_NAME}-{version}-legacy.zip",
    )


def verify_release_surfaces(root: Path, version: str) -> None:
    readme = (root / "README.md").read_text(encoding="utf-8")
    manifest = (root / PACKAGE_NAME / "blender_manifest.toml").read_text(encoding="utf-8")
    project = (root / "pyproject.toml").read_text(encoding="utf-8")
    changelog = (root / "Docs" / "changelogs" / "功能更新日志.md").read_text(
        encoding="utf-8"
    )
    required = {
        "Extension download link": release_urls(version)[0],
        "Legacy download link": release_urls(version)[1],
        "README current source": f"Current_source-{version}",
        "README source statement": f"currently **{version}**",
        "Extension manifest version": f'version = "{version}"',
        "project version": f'version = "{version}"',
        "changelog heading": f"## {version}",
    }
    surfaces = {
        "Extension download link": readme,
        "Legacy download link": readme,
        "README current source": readme,
        "README source statement": readme,
        "Extension manifest version": manifest,
        "project version": project,
        "changelog heading": changelog,
    }
    missing = [label for label, value in required.items() if value not in surfaces[label]]
    if missing:
        raise ValueError(f"Release surfaces are stale or missing: {missing}")
    stale_links = sorted(
        set(
            re.findall(
                rf"releases/latest/download/{PACKAGE_NAME}-(\d+\.\d+\.\d+)(?:-legacy)?\.zip",
                readme,
            )
        )
        - {version}
    )
    if stale_links:
        raise ValueError(f"README still contains old download versions: {stale_links}")


def verify_online_release(version: str) -> None:
    for url in release_urls(version):
        request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": PACKAGE_NAME})
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise ValueError(f"Release asset is unavailable ({response.status}): {url}")


def run_gate(root: Path, *, verify_online: bool = False) -> None:
    root = root.resolve()
    version = read_project_version(root)
    extension = root / "dist" / f"{PACKAGE_NAME}-{version}.zip"
    legacy = root / "dist" / f"{PACKAGE_NAME}-{version}-legacy.zip"
    for path in (extension, legacy):
        if not path.is_file():
            raise FileNotFoundError(f"Required package is missing: {path}")
    verify_package_parity(extension, legacy)
    verify_release_surfaces(root, version)
    if verify_online:
        verify_online_release(version)
    print(
        f"RELEASE_GATE_OK version={version} files="
        f"{len(archive_payload(legacy, legacy=True))} online={verify_online}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify Extension/Legacy parity and release-facing version surfaces."
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--verify-online",
        action="store_true",
        help="Also require both assets to exist under the latest GitHub Release.",
    )
    args = parser.parse_args()
    run_gate(args.root, verify_online=args.verify_online)


if __name__ == "__main__":
    main()
