"""Blender Extension entry point."""

from __future__ import annotations

bl_info = {
    "name": "Render All Cameras",
    "author": "Seker800",
    "version": (0, 1, 0),
    "blender": (4, 5, 0),
    "location": "Properties > Output > Render All Cameras",
    "description": "Render still images from every camera in the current scene",
    "category": "Render",
}


def register() -> None:
    from .presentation import register as register_presentation

    register_presentation()


def unregister() -> None:
    from .presentation import unregister as unregister_presentation

    unregister_presentation()
