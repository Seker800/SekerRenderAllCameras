from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import bpy

from ..application import BatchCoordinator, RenderAction
from ..domain import BatchStatus, Channel, ResultStatus
from ..domain.naming import fit_path, output_filename
from ..infrastructure.manifest import AtomicJsonWriter
from ..infrastructure.storage import (
    BatchAllocation,
    allocate_batch,
    mark_complete,
    mark_incomplete,
)
from .render_adapter import BlenderRenderAdapter
from .scene_reader import build_render_plan, validate_scene
from .state_transaction import BlenderStateTransaction


@dataclass(slots=True)
class BlenderBatchSession:
    scene: bpy.types.Scene
    allocation: BatchAllocation
    coordinator: BatchCoordinator
    adapter: BlenderRenderAdapter
    transaction: BlenderStateTransaction
    manifest: AtomicJsonWriter
    action_started_at: float = 0.0
    started_at: str = ""

    def start(self) -> RenderAction | None:
        self.started_at = datetime.now(timezone.utc).isoformat()
        action = self.coordinator.start()
        self.write_manifest()
        return action

    def prepare_current(self) -> bool:
        action = self.coordinator.current_action
        if action is None:
            raise RuntimeError("batch has no pending action")
        self.action_started_at = time.monotonic()
        return self.adapter.prepare(action)

    def complete_current(self) -> RenderAction | None:
        elapsed = max(0.0, time.monotonic() - self.action_started_at)
        completed_action = self.coordinator.current_action
        completed_channel = completed_action.channel
        self.adapter.finalize_output(completed_action)
        next_action = self.coordinator.complete_current(
            ResultStatus.SUCCEEDED, elapsed_seconds=elapsed
        )
        self.adapter.cleanup_auxiliary()
        if completed_channel is Channel.OBJECT_ID:
            self.write_object_id_manifest()
        self.write_manifest()
        return next_action

    def fail(self, error: str) -> None:
        self.adapter.cleanup_auxiliary()
        self.coordinator.fail(error)
        self.write_manifest()

    def fail_current(self, error: str) -> RenderAction | None:
        self.adapter.cleanup_auxiliary()
        next_action = self.coordinator.complete_current(ResultStatus.FAILED, error=error)
        self.write_manifest()
        return next_action

    def cancel(self) -> None:
        self.adapter.cleanup_auxiliary()
        self.coordinator.cancel_now()
        self.write_manifest()

    def finish(self) -> None:
        self.adapter.cleanup_auxiliary()
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
            "addon_version": "0.2.0",
            "blender_version": bpy.app.version_string,
            "status": progress.status.value,
            "batch": self.coordinator.plan.batch_label,
            "blend_file": str(self.coordinator.plan.blend_path),
            "scene": self.coordinator.plan.scene_name,
            "frame": self.coordinator.plan.frame,
            "camera_count": progress.camera_count,
            "cancel_requested": progress.cancel_requested,
            "error": progress.error,
            "started_at": self.started_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "settings": {
                "engine": self.coordinator.plan.settings.engine,
                "width": self.coordinator.plan.settings.width,
                "height": self.coordinator.plan.settings.height,
                "format": self.coordinator.plan.settings.file_format,
                "samples": self.coordinator.plan.settings.samples,
                "film_transparent": self.coordinator.plan.settings.film_transparent,
            },
            "channels": [channel.value for channel in self.coordinator.plan.channels],
            "cameras": [
                {"key": camera.key, "name": camera.display_name, "output_name": camera.output_name}
                for camera in self.coordinator.plan.cameras
            ],
            "known_limitations": [
                "Volume objects are excluded from Object ID",
                "Third-party render engines are only guaranteed for Beauty after validation",
            ],
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

    def write_object_id_manifest(self) -> None:
        if not self.adapter.id_colors:
            return
        path = self.allocation.directory / (
            f"{self.coordinator.plan.batch_label}_{self.coordinator.plan.blend_name}_ObjectID.json"
        )
        AtomicJsonWriter(path).write(
            {
                "schema_version": 1,
                "background": "#000000",
                "objects": [
                    {"key": color.key, "rgb": list(color.rgb), "hex": color.hex}
                    for color in self.adapter.id_colors
                ],
                "skipped": self.adapter.id_skipped,
            }
        )


def create_session(
    scene: bpy.types.Scene,
    *,
    batch_start: int,
    include_alpha: bool,
    include_object_id: bool,
) -> BlenderBatchSession:
    validate_scene(scene, include_alpha=include_alpha, include_object_id=include_object_id)
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
            adapter=BlenderRenderAdapter(scene),
            transaction=transaction,
            manifest=AtomicJsonWriter(
                allocation.directory / f"{plan.batch_label}_{plan.blend_name}_RenderInfo.json"
            ),
        )
    except Exception:
        mark_incomplete(allocation)
        raise


def run_beauty_batch_sync(scene: bpy.types.Scene, batch_start: int = 1) -> BlenderBatchSession:
    return run_batch_sync(scene, batch_start=batch_start)


def run_batch_sync(
    scene: bpy.types.Scene,
    *,
    batch_start: int = 1,
    include_alpha: bool = False,
    include_object_id: bool = False,
) -> BlenderBatchSession:
    session = create_session(
        scene,
        batch_start=batch_start,
        include_alpha=include_alpha,
        include_object_id=include_object_id,
    )
    try:
        session.start()
        while session.coordinator.current_action is not None:
            if session.prepare_current():
                session.adapter.render_sync()
            session.complete_current()
    except Exception as exc:
        session.fail(str(exc))
        raise
    finally:
        session.finish()
    return session
