from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_cross_version_contracts import verify_contracts


class CrossVersionContractTests(unittest.TestCase):
    def test_accepts_equal_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / "4.0.2.json", root / "5.2.1.json"]
            for path in paths:
                path.write_text(json.dumps({"channels": ["Beauty"]}), encoding="utf-8")
            verify_contracts(paths)

    def test_rejects_contract_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "4.0.2.json"
            second = root / "5.2.1.json"
            first.write_text(json.dumps({"channels": ["Beauty"]}), encoding="utf-8")
            second.write_text(json.dumps({"channels": ["Alpha"]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "contract differs"):
                verify_contracts([first, second])


if __name__ == "__main__":
    unittest.main()
