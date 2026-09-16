from __future__ import annotations

from typing import Any

_MISSING = object()


def is_editable_id(data_block: Any) -> bool:
    """Return whether an ID can be edited across supported Blender versions."""
    editable = getattr(data_block, "is_editable", _MISSING)
    if editable is not _MISSING:
        return bool(editable)

    # Blender 4.0 does not expose ID.is_editable. Local IDs and library
    # overrides are editable there; directly linked IDs are not.
    return data_block.library is None or data_block.override_library is not None


def set_scene_compositing(scene: Any, *, enabled: bool) -> None:
    """Enable or disable compositing across Blender's 4.x/5.x scene APIs."""
    render = scene.render
    if hasattr(render, "use_compositing"):
        render.use_compositing = enabled
    else:
        scene.use_nodes = enabled
