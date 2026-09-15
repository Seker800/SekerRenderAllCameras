from __future__ import annotations

from ..blender.runtime import BlenderBatchSession

active_session: BlenderBatchSession | None = None
render_event: str | None = None
active_operator: object | None = None


def clear() -> None:
    global active_operator, active_session, render_event
    active_session = None
    render_event = None
    active_operator = None
