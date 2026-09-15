from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..domain import (
    BatchStatus,
    Channel,
    ChannelResult,
    JobProgress,
    RenderPlan,
    ResultStatus,
)


@dataclass(frozen=True, slots=True)
class RenderAction:
    camera_key: str
    camera_name: str
    channel: Channel
    output_path: Path


class BatchCoordinator:
    """Single owner of batch progress; host callbacks only feed completion events."""

    def __init__(self, plan: RenderPlan, outputs: dict[tuple[str, Channel], Path]):
        self.plan = plan
        self._actions = tuple(
            RenderAction(camera.key, camera.display_name, channel, outputs[(camera.key, channel)])
            for camera in plan.cameras
            for channel in plan.channels
        )
        self._cursor = 0
        self._results: list[ChannelResult] = []
        self._status = BatchStatus.IDLE
        self._cancel_requested = False
        self._error: str | None = None
        self._had_failures = False

    def start(self) -> RenderAction | None:
        if self._status is not BatchStatus.IDLE:
            raise RuntimeError("batch already started")
        self._status = BatchStatus.IN_PROGRESS
        if not self._actions:
            self._status = BatchStatus.COMPLETED
        return self.current_action

    @property
    def current_action(self) -> RenderAction | None:
        return self._actions[self._cursor] if self._cursor < len(self._actions) else None

    @property
    def is_finished(self) -> bool:
        return self._status in {
            BatchStatus.COMPLETED,
            BatchStatus.CANCELLED,
            BatchStatus.FAILED,
        }

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def complete_current(
        self,
        status: ResultStatus,
        *,
        elapsed_seconds: float = 0.0,
        error: str | None = None,
    ) -> RenderAction | None:
        action = self.current_action
        if action is None:
            raise RuntimeError("no current render action")
        self._results.append(
            ChannelResult(
                camera_key=action.camera_key,
                camera_name=action.camera_name,
                channel=action.channel,
                path=action.output_path,
                status=status,
                elapsed_seconds=elapsed_seconds,
                error=error,
            )
        )
        self._cursor += 1
        if status is ResultStatus.FAILED:
            self._had_failures = True
            self._error = error or "one or more renders failed"
        if self._cancel_requested:
            self._status = BatchStatus.CANCELLED
        elif self._cursor >= len(self._actions):
            self._status = BatchStatus.FAILED if self._had_failures else BatchStatus.COMPLETED
        return self.current_action if not self.is_finished else None

    def fail(self, error: str) -> None:
        self._error = error
        self._status = BatchStatus.FAILED

    def cancel_now(self) -> None:
        self._cancel_requested = True
        self._status = BatchStatus.CANCELLED

    def snapshot(self) -> JobProgress:
        action = self.current_action
        camera_index = 0
        if action is not None:
            camera_index = next(
                index
                for index, camera in enumerate(self.plan.cameras)
                if camera.key == action.camera_key
            )
        elif self.plan.cameras:
            camera_index = len(self.plan.cameras) - 1
        return JobProgress(
            status=self._status,
            camera_index=camera_index,
            camera_count=len(self.plan.cameras),
            current_camera=action.camera_name if action else None,
            current_channel=action.channel if action else None,
            cancel_requested=self._cancel_requested,
            results=tuple(self._results),
            error=self._error,
        )
