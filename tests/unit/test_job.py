import unittest
from pathlib import Path

from camera_batch_renderer.application.job import BatchJob, JobStep
from camera_batch_renderer.domain import (
    BatchStatus,
    CameraSpec,
    Channel,
    ConflictPolicy,
    RenderPlan,
    RenderSettings,
)


def make_plan() -> RenderPlan:
    return RenderPlan(
        batch_number=1,
        batch_label="001",
        blend_path=Path("file.blend"),
        blend_name="file",
        output_directory=Path("RenderOutput/001"),
        scene_name="Scene",
        view_layer_name="ViewLayer",
        frame=1,
        cameras=(CameraSpec("a", "A", "A"), CameraSpec("b", "B", "B")),
        channels=(Channel.BEAUTY,),
        settings=RenderSettings("CYCLES", "Cycles", 100, 100, "PNG", ".png"),
        conflict_policy=ConflictPolicy.NEXT_BATCH,
    )


class JobTests(unittest.TestCase):
    def test_normal_completion(self):
        job = BatchJob(make_plan())
        self.assertEqual(job.start(), JobStep.PREPARING_CAMERA)
        self.assertEqual(job.next_after_camera(), JobStep.PREPARING_CAMERA)
        self.assertEqual(job.next_after_camera(), JobStep.RESTORING)
        job.finish_restoration()
        self.assertEqual(job.progress.status, BatchStatus.COMPLETED)

    def test_cancellation_restores_before_finishing(self):
        job = BatchJob(make_plan())
        job.start()
        job.request_cancel()
        self.assertEqual(job.next_after_camera(), JobStep.RESTORING)
        job.finish_restoration()
        self.assertEqual(job.progress.status, BatchStatus.CANCELLED)


if __name__ == "__main__":
    unittest.main()
