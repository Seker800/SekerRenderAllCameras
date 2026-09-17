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


def read_release_contract(root: Path) -> dict:
    contract = json.loads(
        (root / "packaging" / "release_contract.json").read_text(encoding="utf-8")
    )
    if contract.get("schema_version") != 1 or contract.get("module_id") != PACKAGE_NAME:
        raise ValueError("Release contract schema or module_id is invalid")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", contract.get("asset_stem", "")):
        raise ValueError("Release contract asset_stem is invalid")
    if set(contract.get("output_options", {})) != {
        "include_beauty",
        "include_alpha",
        "include_object_id",
        "include_material_id",
    }:
        raise ValueError("Release contract must define all four output options")
    return contract


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
        name for name in extension_names if extension_payload[name] != legacy_payload[name]
    )
    if different:
        raise ValueError(f"Package contents differ: {different}")


def target_artifact_paths(root: Path, version: str) -> list[tuple[dict[str, str], Path]]:
    contract = read_release_contract(root)
    config = json.loads((root / "packaging" / "blender_targets.json").read_text(encoding="utf-8"))
    return [
        (
            target,
            root / "dist" / f"{contract['asset_stem']}-{version}-{target['id']}.zip",
        )
        for target in config["targets"]
    ]


def _version_tuple_source(value: str) -> bytes:
    parts = tuple(int(part) for part in value.split("."))
    return repr(parts).encode()


def target_display_name(contract: dict, version: str, target: dict) -> str:
    blender_label = target["id"].removeprefix("blender-").replace("-lts", " LTS")
    return f"{contract['display_name']} {version} (Blender {blender_label})"


def verify_feature_surface(payload: dict[str, bytes], contract: dict) -> None:
    properties = payload.get("presentation/properties.py", b"").decode("utf-8")
    panel = payload.get("presentation/panel.py", b"").decode("utf-8")
    for property_name, option in contract["output_options"].items():
        declaration = (
            rf"\b{re.escape(property_name)}\s*:\s*bpy\.props\.BoolProperty\("
            rf'\s*name="{re.escape(option["label"])}",\s*'
            rf"default={option['default']}\s*\)"
        )
        if re.search(declaration, properties) is None:
            raise ValueError(
                f"Package output option is missing or has the wrong default: {property_name}"
            )
        if re.search(rf'\.prop\(settings, "{re.escape(property_name)}"\)', panel) is None:
            raise ValueError(f"Package UI does not draw output option: {property_name}")


def verify_target_packages(root: Path, version: str) -> list[Path]:
    contract = read_release_contract(root)
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
        expected_display_name = target_display_name(contract, version, target)
        expected_name = f'"name": "{expected_display_name}"'.encode()
        if expected_name not in entry:
            raise ValueError(f"Add-on display name is wrong: {target['id']}")
        if b'"version": ' + _version_tuple_source(version) not in entry:
            raise ValueError(f"Add-on version is wrong: {target['id']}")
        expected_bl_info = b'"blender": ' + _version_tuple_source(target["version_min"])
        if expected_bl_info not in entry:
            raise ValueError(f"Entry point has the wrong Blender minimum: {target['id']}")
        if target["package_type"] == "extension":
            if manifest is None:
                raise ValueError(f"Extension manifest is missing: {target['id']}")
            manifest_text = manifest.decode("utf-8")
            for key, expected in (
                ("id", contract["module_id"]),
                ("name", expected_display_name),
                ("version", version),
            ):
                if f'{key} = "{expected}"' not in manifest_text:
                    raise ValueError(f"Manifest {key} is wrong: {target['id']}")
            for key in ("version_min", "version_max"):
                expected = f'blender_{key} = "{target[key]}"'
                if expected not in manifest_text:
                    raise ValueError(f"Manifest does not contain {expected}: {target['id']}")
        elif manifest is not None:
            raise ValueError(f"Legacy target contains an Extension manifest: {target['id']}")
        verify_feature_surface(payload, contract)
        if reference is None:
            reference = payload
        elif payload != reference:
            differing = sorted(set(payload) ^ set(reference))
            differing.extend(
                name for name in set(payload) & set(reference) if payload[name] != reference[name]
            )
            raise ValueError(f"Shared package contents differ for {target['id']}: {differing}")
        paths.append(path)
    return paths


def release_urls(root: Path, version: str) -> tuple[str, ...]:
    base = f"https://github.com/{GITHUB_REPOSITORY}/releases/latest/download"
    return tuple(f"{base}/{path.name}" for _target, path in target_artifact_paths(root, version))


def verify_release_surfaces(root: Path, version: str) -> None:
    contract = read_release_contract(root)
    readme = (root / "README.md").read_text(encoding="utf-8")
    manifest = (root / PACKAGE_NAME / "blender_manifest.toml").read_text(encoding="utf-8")
    project = (root / "pyproject.toml").read_text(encoding="utf-8")
    changelog = (root / "Docs" / "changelogs" / "功能更新日志.md").read_text(encoding="utf-8")
    required = {
        **{
            f"Target download link {index + 1}": url
            for index, url in enumerate(release_urls(root, version))
        },
        **{
            f"Target display name {index + 1}": target_display_name(
                contract, version, target
            ).replace(" (Blender ", " · Blender ").rstrip(")")
            for index, (target, _path) in enumerate(target_artifact_paths(root, version))
        },
        "README current source": f"Current_source-{version}",
        "README source statement": f"currently **{version}**",
        "Extension manifest version": f'version = "{version}"',
        "project version": f'version = "{version}"',
        "changelog heading": f"## {version}",
        "README display name": contract["display_name"],
    }
    surfaces = {
        **{
            f"Target download link {index + 1}": readme
            for index, _url in enumerate(release_urls(root, version))
        },
        **{
            f"Target display name {index + 1}": readme
            for index, _item in enumerate(target_artifact_paths(root, version))
        },
        "README current source": readme,
        "README source statement": readme,
        "Extension manifest version": manifest,
        "project version": project,
        "changelog heading": changelog,
        "README display name": readme,
    }
    missing = [label for label, value in required.items() if value not in surfaces[label]]
    if missing:
        raise ValueError(f"Release surfaces are stale or missing: {missing}")
    actual_links = set(
        re.findall(
            rf"https://github\.com/{re.escape(GITHUB_REPOSITORY)}"
            r"/releases/latest/download/[^\s\"')]+\.zip",
            readme,
        )
    )
    if actual_links != set(release_urls(root, version)):
        raise ValueError("README download links differ from the five release artifacts")


def verify_online_release(root: Path, version: str) -> None:
    artifacts = target_artifact_paths(root, version)
    release_request = urllib.request.Request(
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest",
        headers={"User-Agent": PACKAGE_NAME, "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(release_request, timeout=30) as response:
        if response.status != 200:
            raise ValueError(f"Cannot read latest GitHub Release ({response.status})")
        latest = json.load(response)
    expected_names = {path.name for _target, path in artifacts}
    actual_names = {asset["name"] for asset in latest.get("assets", [])}
    if (
        latest.get("tag_name") != f"v{version}"
        or latest.get("draft")
        or latest.get("prerelease")
        or actual_names != expected_names
    ):
        raise ValueError("Latest GitHub Release tag or assets differ from this tested version")
    for url, (_target, local_path) in zip(release_urls(root, version), artifacts, strict=True):
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


def run_gate(root: Path, *, verify_online: bool = False, packages_only: bool = False) -> None:
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
