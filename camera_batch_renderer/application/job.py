from __future__ import annotations

from dataclasses import replace

from ..domain import BatchStatus, JobProgress, RenderPlan
from ..domain.compat import StrEnum


class JobStep(StrEnum):
    IDLE = "idle"
    PREPARING_CAMERA = "preparing_camera"
    BEAUTY = "beauty"
    ALPHA = "alpha"
    OBJECT_ID = "object_id"
    ADVANCING = "advancing"
    RESTORING = "restoring"
    FINISHED = "finished"


class JobEvent(StrEnum):
    START = "start"
    STEP_SUCCEEDED = "step_succeeded"
    STEP_FAILED = "step_failed"
    CANCEL = "cancel"
    RESTORED = "restored"


class BatchJob:
    """Pure transition model. Blender callbacks execute the work between transitions."""

    def __init__(self, plan: RenderPlan):
        self.plan = plan
        self.step = JobStep.IDLE
        self.progress = JobProgress(
            status=BatchStatus.IDLE,
            camera_index=0,
            camera_count=len(plan.cameras),
            current_camera=None,
            current_channel=None,
            cancel_requested=False,
        )

    def request_cancel(self) -> None:
        self.progress = replace(self.progress, cancel_requested=True)

    def start(self) -> JobStep:
        if self.step is not JobStep.IDLE:
            raise RuntimeError("job already started")
        self.step = JobStep.PREPARING_CAMERA
        camera = self.plan.cameras[0] if self.plan.cameras else None
        self.progress = replace(
            self.progress,
            status=BatchStatus.IN_PROGRESS,
            current_camera=camera.display_name if camera else None,
        )
        return self.step

    def next_after_camera(self) -> JobStep:
        if self.progress.cancel_requested:
            self.step = JobStep.RESTORING
            return self.step
        next_index = self.progress.camera_index + 1
        if next_index >= len(self.plan.cameras):
            self.step = JobStep.RESTORING
            return self.step
        self.step = JobStep.PREPARING_CAMERA
        self.progress = replace(
            self.progress,
            camera_index=next_index,
            current_camera=self.plan.cameras[next_index].display_name,
            current_channel=None,
        )
        return self.step

    def finish_restoration(self, error: str | None = None) -> JobStep:
        status = (
            BatchStatus.FAILED
            if error
            else (
                BatchStatus.CANCELLED if self.progress.cancel_requested else BatchStatus.COMPLETED
            )
        )
        self.step = JobStep.FINISHED
        self.progress = replace(self.progress, status=status, current_channel=None, error=error)
        return self.step
