from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from camera_batch_renderer import application, domain, infrastructure, version
from camera_batch_renderer.infrastructure.storage import prepare_output_directory


class SessionFailureTests(unittest.TestCase):
    def setUp(self):
        prefix = "_rac_session_test"
        modules = {prefix: ModuleType(prefix), "bpy": SimpleNamespace(),
                   f"{prefix}.application": application, f"{prefix}.domain": domain,
                   f"{prefix}.infrastructure": infrastructure, f"{prefix}.version": version,
                   f"{prefix}.blender": ModuleType(f"{prefix}.blender")}
        for name, attributes in {
            "render_adapter": ("BlenderRenderAdapter",),
            "scene_reader": ("build_render_plan", "validate_scene"),
            "state_transaction": ("BlenderStateTransaction",),
        }.items():
            module = ModuleType(f"{prefix}.blender.{name}")
            for attribute in attributes:
                setattr(module, attribute, Mock())
            modules[module.__name__] = module
        spec = importlib.util.spec_from_file_location(
            f"{prefix}.blender.runtime",
            Path(__file__).parents[2] / "camera_batch_renderer/blender/runtime.py",
        )
        self.api = importlib.util.module_from_spec(spec)
        modules[spec.name] = self.api
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(self.api)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        allocation = prepare_output_directory(Path(self.temporary.name))
        self.session = self.api.BlenderBatchSession(
            scene=Mock(), allocation=allocation, staging_directory=allocation.staging_directory,
            coordinator=Mock(), adapter=Mock(), transaction=Mock(), manifest=Mock(),
        )
        self.session.coordinator.snapshot.return_value = SimpleNamespace(
            status=domain.BatchStatus.COMPLETED)

    def test_auxiliary_cleanup_failure_still_restores_host_state(self):
        self.session.adapter.cleanup_auxiliary.side_effect = RuntimeError("cleanup failed")
        with patch.object(self.api.BlenderBatchSession, "write_manifest"), \
                self.assertRaisesRegex(RuntimeError, "cleanup failed"):
            self.session.finish()
        self.session.transaction.restore.assert_called_once()
        self.session.coordinator.fail.assert_called_once()
        self.assertTrue((self.session.allocation.working_directory / ".incomplete").exists())

    def test_committed_action_manifest_failure_is_batch_fatal(self):
        self.session.coordinator.current_action = SimpleNamespace(channel=domain.Channel.BEAUTY)
        with patch.object(self.api.BlenderBatchSession, "write_manifest",
                          side_effect=OSError("disk full")):
            with self.assertRaisesRegex(Exception, "disk full"):
                self.session.complete_current()
        self.session.coordinator.fail.assert_called_once()

    def test_staging_cleanup_failure_is_not_silently_successful(self):
        def locked_remove(_path, *, ignore_errors=False):
            if not ignore_errors:
                raise PermissionError("locked staging")

        self.session.coordinator.snapshot.return_value.status = domain.BatchStatus.CANCELLED
        with patch.object(self.api.BlenderBatchSession, "write_manifest"), patch.object(
            self.api.shutil, "rmtree", side_effect=locked_remove
        ):
            with self.assertRaisesRegex(Exception, "locked staging"):
                self.session.finish()
        self.session.transaction.restore.assert_called_once()
