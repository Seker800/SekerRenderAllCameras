RENDER_COMPLETE = "complete"
RENDER_CANCELLED = "cancelled"


def resolve_render_event(
    recorded_event: str | None,
    *,
    render_job_running: bool,
    output_exists: bool,
) -> str | None:
    """Resolve a render terminal event without racing Blender job teardown.

    Blender handlers are the primary signal. A successfully written fresh
    staging output is the completion fallback; pre-existing final files never
    count as evidence that the current render completed.
    In both cases the render job must be idle before the next render may start.
    """
    if render_job_running:
        return None
    if recorded_event == RENDER_CANCELLED:
        return RENDER_CANCELLED
    if recorded_event == RENDER_COMPLETE or output_exists:
        return RENDER_COMPLETE
    return None
