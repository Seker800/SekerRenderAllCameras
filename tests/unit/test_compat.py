from __future__ import annotations

import json
import unittest

from camera_batch_renderer.domain.compat import StrEnum


class ExampleValue(StrEnum):
    ITEM = "item"


class StrEnumCompatibilityTests(unittest.TestCase):
    def test_behaves_like_a_string_value(self) -> None:
        self.assertEqual(ExampleValue.ITEM, "item")
        self.assertEqual(str(ExampleValue.ITEM), "item")
        self.assertEqual(json.dumps({"value": ExampleValue.ITEM}), '{"value": "item"}')


if __name__ == "__main__":
    unittest.main()
