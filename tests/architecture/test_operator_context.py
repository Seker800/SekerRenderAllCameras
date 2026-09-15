from pathlib import Path
from unittest import TestCase


class OperatorContextTests(TestCase):
    def test_cancel_button_does_not_call_render_view_operator(self) -> None:
        source = (
            Path(__file__).resolve().parents[2]
            / "camera_batch_renderer"
            / "presentation"
            / "operators.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("bpy.ops.render.view_cancel", source)
