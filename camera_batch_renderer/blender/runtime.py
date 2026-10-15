from __future__ import annotations

import shutil
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import bpy

from ..application import BatchCoordinator, RenderAction
from ..domain import BatchStatus, Channel, ResultStatus
from ..domain.naming import OUTPUT_DIRECTORY_NAME, fit_path, output_filename
from ..infrastructure.diagnostics import DiagnosticJournal
from ..infrastructure.manifest import AtomicJsonWriter
from ..infrastructure.storage import (
    OutputAllocation,
    mark_complete,
    mark_incomplete,
    prepare_output_directory,
)
from ..version import VERSION_TEXT
from .render_adapter import BlenderRenderAdapter
from .scene_reader import build_render_plan, validate_scene
from .state_transaction import BlenderStateTransaction


class BatchIntegrityError(RuntimeError):
    """The batch cannot safely continue after a cleanup or bookkeeping failure."""


@dataclass(slots=True)
class BlenderBatchSession:
    scene: bpy.types.Scene
    allocation: OutputAllocation
    staging_directory: Path
    coordinator: BatchCoordinator
    adapter: BlenderRenderAdapter
    transaction: BlenderStateTransaction
    manifest: AtomicJsonWriter
    action_started_at: float = 0.0
    started_at: str = ""
    diagnostics: DiagnosticJournal | None = None

    def record_diagnostic(
        self, event: str, *, heartbeat: bool = False, error: str = "",
        native_event: str | None = None,
    ) -> None:
        if self.diagnostics is None:
            return
        try:
            progress = self.coordinator.snapshot()
            action = self.coordinator.current_action
            self.diagnostics.record(
                event,
                heartbeat=heartbeat,
                status=progress.status.value,
                completed_images=len(progress.results),
                cancel_requested=progress.cancel_requested,
                render_job_running=bpy.app.is_job_running("RENDER"),
                native_event=native_event,
                action=None if action is None else {
                    "camera": action.camera_name,
                    "channel": action.channel.value,
                    "output": str(action.output_path),
                    "staging_exists": self.adapter.has_fresh_output(action),
                },
                error=error or None,
                traceback=traceback.format_exc() if error and sys.exc_info()[0] else None,
            )
            settings = getattr(self.scene, "rac_settings", None)
            if settings is not None:
                settings.diagnostic_error = (
                    f"Cannot update diagnostics: {self.diagnostics.write_error}"
                    if self.diagnostics.write_error else ""
                )
        except Exception as exc:
            print(f"Cannot collect render diagnostics: {exc}", flush=True)

    def start(self) -> RenderAction | None:
        self.started_at = datetime.now(timezone.utc).isoformat()
        action = self.coordinator.start()
        self.record_diagnostic("session_started")
        self.write_manifest()
        return action

    def abort_start(self, error: str) -> str:
        """Roll back a failed launch before any render job has been submitted."""
        self.coordinator.fail(error)
        self.record_diagnostic("start_failed", error=error)
        try:
            self.finish()
        except Exception as cleanup_error:
            return f"{error}; cleanup also failed: {cleanup_error}"
        return error

    def prepare_current(self) -> bool:
        action = self.coordinator.current_action
        if action is None:
            raise RuntimeError("batch has no pending action")
        self.action_started_at = time.monotonic()
        self.record_diagnostic("preparing_image")
        return self.adapter.prepare(action)

    def complete_current(self) -> RenderAction | None:
        elapsed = max(0.0, time.monotonic() - self.action_started_at)
        completed_action = self.coordinator.current_action
        completed_channel = completed_action.channel
        self.adapter.finalize_output(completed_action)
        self.record_diagnostic("image_written")
        next_action = self.coordinator.complete_current(
            ResultStatus.SUCCEEDED, elapsed_seconds=elapsed
        )
        try:
            self.adapter.cleanup_auxiliary()
            if completed_channel is Channel.OBJECT_ID:
                self.write_object_id_manifest()
            elif completed_channel is Channel.MATERIAL_ID:
                self.write_material_id_manifest()
            self.write_manifest()
        except Exception as exc:
            self.coordinator.fail(str(exc))
            raise BatchIntegrityError(str(exc)) from exc
        return next_action

    def fail(self, error: str) -> None:
        self.record_diagnostic("batch_failed", error=error)
        self.coordinator.fail(error)
        self.write_manifest()

    def fail_current(self, error: str) -> RenderAction | None:
        self.record_diagnostic("image_failed", error=error)
        try:
            self.adapter.cleanup_auxiliary()
        except Exception as exc:
            self.coordinator.fail(str(exc))
            raise BatchIntegrityError(str(exc)) from exc
        next_action = self.coordinator.complete_current(ResultStatus.FAILED, error=error)
        self.write_manifest()
        return next_action

    def cancel(self) -> None:
        self.record_diagnostic("cancelled")
        self.coordinator.cancel_now()
        self.write_manifest()

    def finish(self) -> None:
        self.record_diagnostic("restoring")
        errors = []
        # Each restoration step must run even if the preceding step failed.
        for cleanup in (self.adapter.cleanup_auxiliary, self.transaction.restore):
            try:
                cleanup()
            except Exception as exc:
                errors.append(str(exc))
        try:
            if self.staging_directory.exists():
                shutil.rmtree(self.staging_directory)
        except Exception as exc:
            errors.append(str(exc))
        if errors:
            self.coordinator.fail("; ".join(errors))
        try:
            self.write_manifest()
            if not errors and self.coordinator.snapshot().status is BatchStatus.COMPLETED:
                mark_complete(self.allocation)
            else:
                mark_incomplete(self.allocation)
        except Exception as exc:
            self.coordinator.fail(str(exc))
            self.record_diagnostic("cleanup_failed", error=str(exc))
            mark_incomplete(self.allocation)
            raise
        self.record_diagnostic("finished", error="; ".join(errors))
        if errors:
            raise BatchIntegrityError("; ".join(errors))

    def write_manifest(self) -> None:
        progress = self.coordinator.snapshot()
        payload = {
            "schema_version": 2,
            "addon_version": VERSION_TEXT,
            "blender_version": bpy.app.version_string,
            "status": progress.status.value,
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
                {
                    "key": camera.key,
                    "name": camera.display_name,
                    "output_name": camera.output_name,
                    "environment": (
                        {
                            "light_collection": camera.environment.light_collection_name,
                            "light_count": (
                                len(camera.environment.light_object_keys)
                                if camera.environment.light_object_keys is not None
                                else None
                            ),
                            "world": camera.environment.world_name,
                        }
                        if camera.environment is not None
                        else None
                    ),
                }
                for camera in self.coordinator.plan.cameras
            ],
            "known_limitations": [
                "Volume objects are excluded from Object ID",
                "Volume materials are excluded from Material ID",
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
        path = self.allocation.directory / (
            f"{self.coordinator.plan.blend_name}_ObjectID.json"
        )
        AtomicJsonWriter(
            path, temporary_directory=self.allocation.working_directory
        ).write(
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

    def write_material_id_manifest(self) -> None:
        path = self.allocation.directory / (
            f"{self.coordinator.plan.blend_name}_MaterialID.json"
        )
        AtomicJsonWriter(
            path, temporary_directory=self.allocation.working_directory
        ).write(
            {
                "schema_version": 1,
                "background": "#000000",
                "materials": [
                    {
                        "key": color.key,
                        "name": self.adapter.material_id_names[color.key],
                        "rgb": list(color.rgb),
                        "hex": color.hex,
                    }
                    for color in self.adapter.material_id_colors
                ],
                "skipped": self.adapter.material_id_skipped,
            }
        )


def create_session(
    scene: bpy.types.Scene,
    *,
    include_beauty: bool = True,
    include_alpha: bool = False,
    include_object_id: bool = False,
    include_material_id: bool = False,
    diagnostics: DiagnosticJournal | None = None,
    environment_pairs: tuple[
        tuple[bpy.types.Object | None, bpy.types.Collection | None, bpy.types.World | None], ...
    ] = (),
) -> BlenderBatchSession:
    validate_scene(
        scene,
        include_beauty=include_beauty,
        include_alpha=include_alpha,
        include_object_id=include_object_id,
        include_material_id=include_material_id,
    )
    output_directory = Path(bpy.data.filepath).parent / OUTPUT_DIRECTORY_NAME
    plan = build_render_plan(
        scene,
        include_beauty=include_beauty,
        include_alpha=include_alpha,
        include_object_id=include_object_id,
        include_material_id=include_material_id,
        output_directory=output_directory,
        environment_pairs=environment_pairs,
    )
    outputs = {
        (camera.key, channel): output_directory / fit_path(
            output_directory,
            output_filename(blend_name=plan.blend_name, camera_name=camera.output_name,
                            channel=channel, settings=plan.settings),
        )
        for camera in plan.cameras for channel in plan.channels
    }
    if len({str(path).casefold() for path in outputs.values()}) != len(outputs):
        raise ValueError("Render output paths collide; rename the affected cameras")
    allocation = prepare_output_directory(output_directory)
    staging_directory = allocation.staging_directory
    try:
        transaction = BlenderStateTransaction(scene).capture()
        environments = {
            camera.key: camera.environment
            for camera in plan.cameras
            if camera.environment is not None
        }
        return BlenderBatchSession(
            scene=scene,
            allocation=allocation,
            staging_directory=staging_directory,
            coordinator=BatchCoordinator(plan, outputs),
            adapter=BlenderRenderAdapter(
                scene, staging_directory, transaction, environments
            ),
            transaction=transaction,
            manifest=AtomicJsonWriter(
                allocation.directory / f"{plan.blend_name}_RenderInfo.json",
                temporary_directory=allocation.working_directory,
            ),
            diagnostics=diagnostics,
        )
    except Exception:
        shutil.rmtree(staging_directory, ignore_errors=True)
        mark_incomplete(allocation)
        raise


def run_beauty_batch_sync(scene: bpy.types.Scene) -> BlenderBatchSession:
    return run_batch_sync(scene)


def run_batch_sync(
    scene: bpy.types.Scene,
    *,
    include_beauty: bool = True,
    include_alpha: bool = False,
    include_object_id: bool = False,
    include_material_id: bool = False,
    environment_pairs: tuple[
        tuple[bpy.types.Object | None, bpy.types.Collection | None, bpy.types.World | None], ...
    ] = (),
) -> BlenderBatchSession:
    session = create_session(
        scene,
        include_beauty=include_beauty,
        include_alpha=include_alpha,
        include_object_id=include_object_id,
        include_material_id=include_material_id,
        environment_pairs=environment_pairs,
    )
    try:
        session.start()
        while session.coordinator.current_action is not None:
            try:
                if session.prepare_current():
                    session.adapter.render_sync()
                session.complete_current()
            except BatchIntegrityError:
                raise
            except Exception as exc:
                session.fail_current(str(exc))
    except Exception as exc:
        session.fail(str(exc))
        raise
    finally:
        session.finish()
    return session
