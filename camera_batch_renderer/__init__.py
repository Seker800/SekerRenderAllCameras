"""Blender Extension entry point."""

from __future__ import annotations

bl_info = {
    "name": "Render All Cameras",
    "author": "Seker800",
    # Blender 4.0's add-on discovery parses bl_info with ast.literal_eval.
    "version": (0, 5, 1),
    "blender": (4, 0, 2),
    "location": "3D Viewport > Sidebar > Batch Render; Properties > Output",
    "description": "Render still images from every camera in the current scene",
    "category": "Render",
}


def register() -> None:
    from .presentation import register as register_presentation

    register_presentation()


def unregister() -> None:
    from .presentation import unregister as unregister_presentation

    unregister_presentation()
