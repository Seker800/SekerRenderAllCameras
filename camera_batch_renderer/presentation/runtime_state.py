from __future__ import annotations

from camera_batch_renderer.blender.runtime import BlenderBatchSession

active_session: BlenderBatchSession | None = None
render_event: str | None = None


def clear() -> None:
    global active_session, render_event
    active_session = None
    render_event = None
