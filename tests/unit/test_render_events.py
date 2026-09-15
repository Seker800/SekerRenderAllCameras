from unittest import TestCase

from camera_batch_renderer.application import (
    RENDER_CANCELLED,
    RENDER_COMPLETE,
    resolve_render_event,
)


class RenderEventTests(TestCase):
    def test_complete_handler_waits_until_render_job_is_idle(self) -> None:
        self.assertIsNone(
            resolve_render_event(
                RENDER_COMPLETE,
                render_job_running=True,
                output_exists=True,
            )
        )

    def test_complete_handler_advances_when_render_job_is_idle(self) -> None:
        self.assertEqual(
            resolve_render_event(
                RENDER_COMPLETE,
                render_job_running=False,
                output_exists=False,
            ),
            RENDER_COMPLETE,
        )

    def test_written_output_recovers_a_missed_complete_handler(self) -> None:
        self.assertEqual(
            resolve_render_event(
                None,
                render_job_running=False,
                output_exists=True,
            ),
            RENDER_COMPLETE,
        )

    def test_missing_output_does_not_fake_completion(self) -> None:
        self.assertIsNone(
            resolve_render_event(
                None,
                render_job_running=False,
                output_exists=False,
            )
        )

    def test_cancel_waits_for_render_job_teardown(self) -> None:
        self.assertIsNone(
            resolve_render_event(
                RENDER_CANCELLED,
                render_job_running=True,
                output_exists=False,
            )
        )
        self.assertEqual(
            resolve_render_event(
                RENDER_CANCELLED,
                render_job_running=False,
                output_exists=False,
            ),
            RENDER_CANCELLED,
        )
