import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[2] / "camera_batch_renderer"


class ImportBoundaryTests(unittest.TestCase):
    def test_domain_and_application_do_not_import_bpy(self):
        violations = []
        for package in (ROOT / "domain", ROOT / "application"):
            for path in package.glob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import) and any(
                        item.name == "bpy" for item in node.names
                    ):
                        violations.append(path)
                    if isinstance(node, ast.ImportFrom) and node.module == "bpy":
                        violations.append(path)
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
