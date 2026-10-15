import tempfile
import unittest
from pathlib import Path

from camera_batch_renderer.domain.models import Channel, RenderSettings
from camera_batch_renderer.domain.naming import (
    camera_specs,
    fit_path,
    natural_key,
    output_filename,
    sanitize_component,
)


class NamingTests(unittest.TestCase):
    def test_generated_suffix_does_not_collide_with_literal_camera_name(self):
        result = camera_specs((("a", "Cam/A"), ("b", "Cam:A"), ("c", "Cam_A_02")))
        self.assertEqual(len({item.output_name.casefold() for item in result}), 3)

    def test_long_camera_names_stay_distinct_in_final_filenames(self):
        settings = RenderSettings("CYCLES", "Cycles", 32, 32, "PNG", ".png")
        cameras = camera_specs((("a", "C" * 70 + "A"), ("b", "C" * 70 + "B")))
        names = [output_filename(blend_name="shot", camera_name=camera.output_name,
                                 channel=Channel.BEAUTY, settings=settings) for camera in cameras]
        self.assertEqual(len(set(names)), 2)

    def test_path_shortening_preserves_camera_and_channel_identity(self):
        directory = Path("x" * 170)
        first = fit_path(directory, "a" * 100 + "_Beauty.png")
        second = fit_path(directory, "a" * 100 + "_Alpha.png")
        self.assertNotEqual(first, second)

    def test_unicode_numeric_character_does_not_crash_natural_sort(self):
        self.assertIsInstance(natural_key("Camera①²⑩"), tuple)

    def test_natural_sort(self):
        values = ["Camera10", "camera2", "Camera1"]
        self.assertEqual(sorted(values, key=natural_key), ["Camera1", "camera2", "Camera10"])

    def test_sanitize_unicode_and_windows_names(self):
        self.assertEqual(sanitize_component("  客厅 / 主机位  "), "客厅___主机位")
        self.assertEqual(sanitize_component("CON"), "_CON")
        self.assertEqual(sanitize_component("..."), "Unnamed")

    def test_collision_suffix_is_stable(self):
        result = camera_specs((("b", "Cam/A"), ("a", "Cam:A")))
        self.assertEqual([item.output_name for item in result], ["Cam_A", "Cam_A_02"])
        self.assertEqual([item.key for item in result], ["a", "b"])

    def test_filename_contains_contract_fields(self):
        settings = RenderSettings("CYCLES", "Cycles", 1920, 1080, "PNG", ".png", 64)
        name = output_filename(
            blend_name="Room",
            camera_name="Main",
            channel=Channel.BEAUTY,
            settings=settings,
        )
        self.assertEqual(name, "Room_Main_Beauty_1920x1080_Cycles_S64.png")

    def test_material_id_filename_is_png_and_names_the_mapping_kind(self):
        settings = RenderSettings("CYCLES", "Cycles", 1920, 1080, "OPEN_EXR", ".exr", 64)
        name = output_filename(
            blend_name="Room",
            camera_name="Main",
            channel=Channel.MATERIAL_ID,
            settings=settings,
        )
        self.assertEqual(name, "Room_Main_MaterialID_1920x1080_Material.png")

    def test_path_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            fitted = fit_path(Path(directory), "x" * 300 + ".png", max_path=120)
            self.assertLessEqual(len(str(Path(directory) / fitted)), 120)


if __name__ == "__main__":
    unittest.main()
