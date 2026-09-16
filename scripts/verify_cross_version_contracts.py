from __future__ import annotations

import argparse
import json
from pathlib import Path


def verify_contracts(paths: list[Path]) -> None:
    if len(paths) < 2:
        raise ValueError("At least two installed-package contracts are required")
    baseline_path = paths[0]
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    for path in paths[1:]:
        current = json.loads(path.read_text(encoding="utf-8"))
        if current != baseline:
            raise ValueError(
                f"Installed-package contract differs: {path.name} != {baseline_path.name}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("contracts", nargs="+", type=Path)
    args = parser.parse_args()
    verify_contracts(args.contracts)
    print(f"CROSS_VERSION_CONTRACTS_OK count={len(args.contracts)}")


if __name__ == "__main__":
    main()
