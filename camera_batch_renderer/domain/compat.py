"""Compatibility helpers for Blender's bundled Python versions."""

from __future__ import annotations

try:
    from enum import StrEnum
except ImportError:  # Python 3.10, bundled with Blender 4.0 and 4.1.
    from enum import Enum

    class StrEnum(str, Enum):
        """Backport the string behavior needed from Python 3.11's StrEnum."""

        def __str__(self) -> str:
            return str(self.value)


__all__ = ["StrEnum"]
