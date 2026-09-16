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
