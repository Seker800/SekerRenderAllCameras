"""Development policy; release staging replaces this module for each Blender target."""

from __future__ import annotations

from .host_drivers import ModalEventDriver

TARGET_ID = "development"
SUPPORTED_VERSION_MIN = (4, 0, 2)
SUPPORTED_VERSION_MAX = None
HOST_DRIVER_CLASS = ModalEventDriver
OPERATOR_START_RESULT = {"RUNNING_MODAL"}


def ensure_supported_version() -> None:
    if TARGET_ID == "development":
        return
    import bpy  # noqa: PLC0415

    version = tuple(bpy.app.version[:3])
    if version < SUPPORTED_VERSION_MIN or (
        SUPPORTED_VERSION_MAX is not None and version >= SUPPORTED_VERSION_MAX
    ):
        maximum = SUPPORTED_VERSION_MAX or "unbounded"
        raise RuntimeError(
            f"Package {TARGET_ID} supports Blender {SUPPORTED_VERSION_MIN} to {maximum}, "
            f"but Blender {version} is running"
        )
