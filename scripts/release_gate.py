from __future__ import annotations

import argparse
import hashlib
import json
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


def target_artifact_paths(root: Path, version: str) -> list[tuple[dict[str, str], Path]]:
    config = json.loads(
        (root / "packaging" / "blender_targets.json").read_text(encoding="utf-8")
    )
    return [
        (
            target,
            root / "dist" / f"{PACKAGE_NAME}-{version}-{target['id']}.zip",
        )
        for target in config["targets"]
    ]


def _version_tuple_source(value: str) -> bytes:
    parts = tuple(int(part) for part in value.split("."))
    return repr(parts).encode()


def verify_target_packages(root: Path, version: str) -> list[Path]:
    reference: dict[str, bytes] | None = None
    paths = []
    for target, path in target_artifact_paths(root, version):
        if not path.is_file():
            raise FileNotFoundError(f"Required target package is missing: {path}")
        payload = archive_payload(path, legacy=target["package_type"] == "legacy")
        policy = payload.pop("presentation/host_policy.py", None)
        entry = payload.pop("__init__.py", None)
        manifest = payload.pop("blender_manifest.toml", None)
        if policy is None or target["id"].encode() not in policy:
            raise ValueError(f"Target policy is missing or stale: {target['id']}")
        for expected in (
            target["driver"].encode(),
            b"SUPPORTED_VERSION_MIN = " + _version_tuple_source(target["version_min"]),
            b"SUPPORTED_VERSION_MAX = " + _version_tuple_source(target["version_max"]),
        ):
            if expected not in policy:
                raise ValueError(
                    f"Target policy does not contain {expected.decode()}: {target['id']}"
                )
        if entry is None:
            raise ValueError(f"Entry point is missing: {target['id']}")
        expected_bl_info = b'"blender": ' + _version_tuple_source(target["version_min"])
        if expected_bl_info not in entry:
            raise ValueError(
                f"Entry point has the wrong Blender minimum: {target['id']}"
            )
        if target["package_type"] == "extension":
            if manifest is None:
                raise ValueError(f"Extension manifest is missing: {target['id']}")
            manifest_text = manifest.decode("utf-8")
            for key in ("version_min", "version_max"):
                expected = f'blender_{key} = "{target[key]}"'
                if expected not in manifest_text:
                    raise ValueError(f"Manifest does not contain {expected}: {target['id']}")
        elif manifest is not None:
            raise ValueError(f"Legacy target contains an Extension manifest: {target['id']}")
        if reference is None:
            reference = payload
        elif payload != reference:
            differing = sorted(set(payload) ^ set(reference))
            differing.extend(
                name
                for name in set(payload) & set(reference)
                if payload[name] != reference[name]
            )
            raise ValueError(f"Shared package contents differ for {target['id']}: {differing}")
        paths.append(path)
    return paths


def release_urls(root: Path, version: str) -> tuple[str, ...]:
    base = f"https://github.com/{GITHUB_REPOSITORY}/releases/latest/download"
    return tuple(
        f"{base}/{PACKAGE_NAME}-{version}-{target['id']}.zip"
        for target, _path in target_artifact_paths(root, version)
    )


def verify_release_surfaces(root: Path, version: str) -> None:
    readme = (root / "README.md").read_text(encoding="utf-8")
    manifest = (root / PACKAGE_NAME / "blender_manifest.toml").read_text(encoding="utf-8")
    project = (root / "pyproject.toml").read_text(encoding="utf-8")
    changelog = (root / "Docs" / "changelogs" / "功能更新日志.md").read_text(
        encoding="utf-8"
    )
    required = {
        **{
            f"Target download link {index + 1}": url
            for index, url in enumerate(release_urls(root, version))
        },
        "README current source": f"Current_source-{version}",
        "README source statement": f"currently **{version}**",
        "Extension manifest version": f'version = "{version}"',
        "project version": f'version = "{version}"',
        "changelog heading": f"## {version}",
    }
    surfaces = {
        **{
            f"Target download link {index + 1}": readme
            for index, _url in enumerate(release_urls(root, version))
        },
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
                rf"releases/latest/download/{PACKAGE_NAME}-(\d+\.\d+\.\d+)(?:-[^\s\"')]+)?\.zip",
                readme,
            )
        )
        - {version}
    )
    if stale_links:
        raise ValueError(f"README still contains old download versions: {stale_links}")


def verify_online_release(root: Path, version: str) -> None:
    artifacts = target_artifact_paths(root, version)
    for url, (_target, local_path) in zip(
        release_urls(root, version), artifacts, strict=True
    ):
        if not local_path.is_file():
            raise FileNotFoundError(f"Local release artifact is missing: {local_path}")
        request = urllib.request.Request(url, method="GET", headers={"User-Agent": PACKAGE_NAME})
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise ValueError(f"Release asset is unavailable ({response.status}): {url}")
            remote_hash = hashlib.sha256()
            while chunk := response.read(1024 * 1024):
                remote_hash.update(chunk)
        local_hash = hashlib.sha256(local_path.read_bytes()).hexdigest()
        if remote_hash.hexdigest() != local_hash:
            raise ValueError(f"Release asset hash does not match the tested package: {url}")


def run_gate(
    root: Path, *, verify_online: bool = False, packages_only: bool = False
) -> None:
    root = root.resolve()
    version = read_project_version(root)
    packages = verify_target_packages(root, version)
    if not packages_only:
        verify_release_surfaces(root, version)
    if verify_online:
        verify_online_release(root, version)
    print(
        f"RELEASE_GATE_OK version={version} targets={len(packages)} "
        f"packages_only={packages_only} online={verify_online}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify Extension/Legacy parity and release-facing version surfaces."
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--packages-only",
        action="store_true",
        help="Verify all five target artifacts without requiring release-page surfaces.",
    )
    parser.add_argument(
        "--verify-online",
        action="store_true",
        help="Also download all five latest-release assets and match their local SHA-256.",
    )
    args = parser.parse_args()
    run_gate(
        args.root,
        verify_online=args.verify_online,
        packages_only=args.packages_only,
    )


if __name__ == "__main__":
    main()
