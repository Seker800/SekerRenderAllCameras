from pathlib import Path
from unittest import TestCase

from camera_batch_renderer.application import BatchCoordinator
from camera_batch_renderer.domain import (
    BatchStatus,
    CameraSpec,
    Channel,
    RenderPlan,
    RenderSettings,
    ResultStatus,
)


def make_plan() -> RenderPlan:
    return RenderPlan(
        blend_path=Path("shot.blend"),
        blend_name="shot",
        output_directory=Path("out"),
        scene_name="Scene",
        view_layer_name="ViewLayer",
        frame=1,
        cameras=(
            CameraSpec("a", "Camera 1", "Camera_1"),
            CameraSpec("b", "Camera 2", "Camera_2"),
        ),
        channels=(Channel.BEAUTY,),
        settings=RenderSettings("BLENDER_WORKBENCH", "Workbench", 32, 32, "PNG", ".png"),
    )


class CoordinatorTests(TestCase):
    def test_preserves_camera_then_channel_order_for_material_id(self) -> None:
        base = make_plan()
        plan = RenderPlan(
            blend_path=base.blend_path,
            blend_name=base.blend_name,
            output_directory=base.output_directory,
            scene_name=base.scene_name,
            view_layer_name=base.view_layer_name,
            frame=base.frame,
            cameras=base.cameras,
            channels=(Channel.BEAUTY, Channel.OBJECT_ID, Channel.MATERIAL_ID),
            settings=base.settings,
        )
        outputs = {
            (camera.key, channel): Path(f"{camera.key}-{channel.value}.png")
            for camera in plan.cameras
            for channel in plan.channels
        }
        coordinator = BatchCoordinator(plan, outputs)
        actions = []
        action = coordinator.start()
        while action is not None:
            actions.append((action.camera_key, action.channel))
            action = coordinator.complete_current(ResultStatus.SUCCEEDED)
        self.assertEqual(
            actions,
            [
                ("a", Channel.BEAUTY),
                ("a", Channel.OBJECT_ID),
                ("a", Channel.MATERIAL_ID),
                ("b", Channel.BEAUTY),
                ("b", Channel.OBJECT_ID),
                ("b", Channel.MATERIAL_ID),
            ],
        )

    def test_advances_and_completes(self) -> None:
        plan = make_plan()
        outputs = {
            (camera.key, Channel.BEAUTY): Path(f"{camera.key}.png") for camera in plan.cameras
        }
        coordinator = BatchCoordinator(plan, outputs)
        self.assertEqual(coordinator.start().camera_key, "a")
        coordinator.complete_current(ResultStatus.SUCCEEDED)
        self.assertEqual(coordinator.current_action.camera_key, "b")
        coordinator.complete_current(ResultStatus.SUCCEEDED)
        self.assertEqual(coordinator.snapshot().status, BatchStatus.COMPLETED)

    def test_cancel_stops_after_current_action(self) -> None:
        plan = make_plan()
        outputs = {
            (camera.key, Channel.BEAUTY): Path(f"{camera.key}.png") for camera in plan.cameras
        }
        coordinator = BatchCoordinator(plan, outputs)
        coordinator.start()
        coordinator.request_cancel()
        coordinator.complete_current(ResultStatus.SUCCEEDED)
        self.assertEqual(coordinator.snapshot().status, BatchStatus.CANCELLED)
        self.assertIsNone(coordinator.current_action)

    def test_item_failure_continues_then_finishes_failed(self) -> None:
        plan = make_plan()
        outputs = {
            (camera.key, Channel.BEAUTY): Path(f"{camera.key}.png") for camera in plan.cameras
        }
        coordinator = BatchCoordinator(plan, outputs)
        coordinator.start()
        coordinator.complete_current(ResultStatus.FAILED, error="camera failed")
        self.assertEqual(coordinator.current_action.camera_key, "b")
        coordinator.complete_current(ResultStatus.SUCCEEDED)
        self.assertEqual(coordinator.snapshot().status, BatchStatus.FAILED)

    def test_cancel_now_is_terminal(self) -> None:
        plan = make_plan()
        outputs = {
            (camera.key, Channel.BEAUTY): Path(f"{camera.key}.png") for camera in plan.cameras
        }
        coordinator = BatchCoordinator(plan, outputs)
        coordinator.start()
        coordinator.cancel_now()
        self.assertEqual(coordinator.snapshot().status, BatchStatus.CANCELLED)
        self.assertIsNone(coordinator.current_action)
