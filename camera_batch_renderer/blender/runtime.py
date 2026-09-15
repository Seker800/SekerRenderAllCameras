from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import bpy

from camera_batch_renderer.application import BatchCoordinator, RenderAction
from camera_batch_renderer.domain import BatchStatus, Channel, ResultStatus
from camera_batch_renderer.domain.naming import fit_path, output_filename
from camera_batch_renderer.infrastructure.manifest import AtomicJsonWriter
from camera_batch_renderer.infrastructure.storage import (
    BatchAllocation,
    allocate_batch,
    mark_complete,
    mark_incomplete,
)

from .render_adapter import BlenderBeautyAdapter
from .scene_reader import build_render_plan
from .state_transaction import BlenderStateTransaction


@dataclass(slots=True)
class BlenderBatchSession:
    scene: bpy.types.Scene
    allocation: BatchAllocation
    coordinator: BatchCoordinator
    adapter: BlenderBeautyAdapter
    transaction: BlenderStateTransaction
    manifest: AtomicJsonWriter
    action_started_at: float = 0.0

    def start(self) -> RenderAction | None:
        action = self.coordinator.start()
        self.write_manifest()
        return action

    def prepare_current(self) -> RenderAction:
        action = self.coordinator.current_action
        if action is None:
            raise RuntimeError("batch has no pending action")
        if action.channel is not Channel.BEAUTY:
            raise NotImplementedError(f"Channel not available yet: {action.channel.value}")
        self.adapter.prepare(action.camera_key, action.output_path)
        self.action_started_at = time.monotonic()
        return action

    def complete_current(self) -> RenderAction | None:
        elapsed = max(0.0, time.monotonic() - self.action_started_at)
        next_action = self.coordinator.complete_current(
            ResultStatus.SUCCEEDED, elapsed_seconds=elapsed
        )
        self.write_manifest()
        return next_action

    def fail(self, error: str) -> None:
        action = self.coordinator.current_action
        if action is not None:
            self.coordinator.complete_current(ResultStatus.FAILED, error=error)
        else:
            self.coordinator.fail(error)
        self.write_manifest()

    def finish(self) -> None:
        self.transaction.restore()
        if self.coordinator.snapshot().status is BatchStatus.COMPLETED:
            mark_complete(self.allocation)
        else:
            mark_incomplete(self.allocation)
        self.write_manifest()

    def write_manifest(self) -> None:
        progress = self.coordinator.snapshot()
        payload = {
            "schema_version": 1,
            "status": progress.status.value,
            "batch": self.coordinator.plan.batch_label,
            "blend_file": str(self.coordinator.plan.blend_path),
            "scene": self.coordinator.plan.scene_name,
            "frame": self.coordinator.plan.frame,
            "camera_count": progress.camera_count,
            "cancel_requested": progress.cancel_requested,
            "error": progress.error,
            "results": [
                {
                    "camera": result.camera_name,
                    "camera_key": result.camera_key,
                    "channel": result.channel.value,
                    "path": str(result.path),
                    "status": result.status.value,
                    "elapsed_seconds": round(result.elapsed_seconds, 3),
                    "error": result.error,
                }
                for result in progress.results
            ],
        }
        self.manifest.write(payload)


def create_session(
    scene: bpy.types.Scene,
    *,
    batch_start: int,
    include_alpha: bool,
    include_object_id: bool,
) -> BlenderBatchSession:
    if not bpy.data.filepath:
        raise ValueError("Save the .blend file before rendering")
    root = Path(bpy.data.filepath).parent / "RenderOutput"
    allocation = allocate_batch(root, batch_start)
    try:
        plan = build_render_plan(
            scene,
            batch_number=allocation.number,
            include_alpha=include_alpha,
            include_object_id=include_object_id,
            output_directory=allocation.directory,
        )
        outputs = {
            (camera.key, channel): allocation.directory
            / fit_path(
                allocation.directory,
                output_filename(
                    batch_label=plan.batch_label,
                    blend_name=plan.blend_name,
                    camera_name=camera.output_name,
                    channel=channel,
                    settings=plan.settings,
                ),
            )
            for camera in plan.cameras
            for channel in plan.channels
        }
        transaction = BlenderStateTransaction(scene).capture()
        return BlenderBatchSession(
            scene=scene,
            allocation=allocation,
            coordinator=BatchCoordinator(plan, outputs),
            adapter=BlenderBeautyAdapter(scene),
            transaction=transaction,
            manifest=AtomicJsonWriter(allocation.directory / "manifest.json"),
        )
    except Exception:
        mark_incomplete(allocation)
        raise


def run_beauty_batch_sync(scene: bpy.types.Scene, batch_start: int = 1) -> BlenderBatchSession:
    session = create_session(
        scene, batch_start=batch_start, include_alpha=False, include_object_id=False
    )
    try:
        session.start()
        while session.coordinator.current_action is not None:
            session.prepare_current()
            session.adapter.render_sync()
            session.complete_current()
    except Exception as exc:
        session.fail(str(exc))
        raise
    finally:
        session.finish()
    return session
