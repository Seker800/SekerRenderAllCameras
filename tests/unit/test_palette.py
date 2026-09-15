import unittest

from camera_batch_renderer.domain.palette import allocate_colors


class PaletteTests(unittest.TestCase):
    def test_colors_are_deterministic_unique_and_not_black(self):
        keys = ["Mesh:A", "Mesh:B", "Mesh:C"]
        first = allocate_colors(keys)
        second = allocate_colors(reversed(keys))
        self.assertEqual(first, second)
        colors = [item.rgb for item in first]
        self.assertEqual(len(colors), len(set(colors)))
        self.assertNotIn((0, 0, 0), colors)
        self.assertTrue(all(item.hex.startswith("#") and len(item.hex) == 7 for item in first))


if __name__ == "__main__":
    unittest.main()
