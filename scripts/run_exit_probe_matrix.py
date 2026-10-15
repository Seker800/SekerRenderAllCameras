"""Launch serialized probes in disposable profiles; preserve all exit codes and logs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def profile_hashes():
    root = Path(os.environ["APPDATA"]) / "Blender Foundation/Blender"
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for pattern in ("[0-9]*.[0-9]*/config/userpref.blend", "[0-9]*.[0-9]*/config/startup.blend")
        for path in sorted(root.glob(pattern))
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", action="append", required=True, help="label=executable")
    parser.add_argument(
        "--modes", nargs="+", default=["native", "oiio", "registered", "unregistered"]
    )
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--engine", default="BLENDER_WORKBENCH")
    parser.add_argument("--factory-reset", choices=["0", "1"], default="1")
    parser.add_argument("--backend", choices=["opengl", "vulkan"])
    parser.add_argument("--probe", default="probe_render_exit.py")
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--require-success", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = args.output.resolve()
    report.mkdir(parents=True, exist_ok=False)
    before = profile_hashes()
    results = []
    (report / "protected-before.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
    try:
        for blender in args.blender:
            label, executable = blender.split("=", 1)
            for mode in args.modes:
                for repeat in range(args.repeat):
                    case = report / f"{label}-{mode}-{repeat + 1}"
                    case.mkdir()
                    env = dict(os.environ)
                    for suffix in ("CONFIG", "SCRIPTS", "DATAFILES", "EXTENSIONS", "RESOURCES"):
                        directory = case / suffix
                        directory.mkdir()
                        env[f"BLENDER_USER_{suffix}"] = str(directory)
                    temporary = case / "temp"
                    temporary.mkdir()
                    env.update(
                        TEMP=str(temporary),
                        TMP=str(temporary),
                        RAC_EXIT_MODE=mode,
                        RAC_EXIT_OUTPUT=str(case),
                        RAC_EXIT_ENGINE=args.engine,
                        RAC_EXIT_FACTORY_RESET=args.factory_reset,
                    )
                    startup = subprocess.STARTUPINFO()
                    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startup.wShowWindow = 0
                    started = time.monotonic()
                    with (
                        (case / "stdout.log").open("w", encoding="utf-8") as stdout,
                        (case / "stderr.log").open("w", encoding="utf-8") as stderr,
                    ):
                        process = subprocess.Popen(
                            [executable]
                            + (["--background"] if args.background else [])
                            + (["--gpu-backend", args.backend] if args.backend else [])
                            + [
                                "--factory-startup",
                                "--python-exit-code",
                                "1",
                                "--python",
                                str(ROOT / "scripts" / args.probe),
                            ],
                            env=env,
                            cwd=ROOT,
                            startupinfo=startup,
                            stdout=stdout,
                            stderr=stderr,
                        )
                        try:
                            code = process.wait(timeout=args.timeout)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                            code = 124
                    item = {
                        "version": label,
                        "mode": mode,
                        "repeat": repeat + 1,
                        "exit_code": code,
                        "render_ok": (case / "before-exit.json").is_file(),
                        "seconds": round(time.monotonic() - started, 2),
                        "case": str(case),
                    }
                    results.append(item)
                    print(json.dumps(item), flush=True)
                    (report / "results.json").write_text(
                        json.dumps(results, indent=2), encoding="utf-8"
                    )
    finally:
        after = profile_hashes()
        summary = {
            "results": results,
            "before": before,
            "after": after,
            "protected_profiles_unchanged": before == after,
            "backend": args.backend,
        }
        (report / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        if before != after:
            raise RuntimeError("Protected Blender profiles changed")
    all_passed = all(item["exit_code"] == 0 and item["render_ok"] for item in results)
    if all_passed:
        print("EXIT_PROBE_MATRIX_OK", flush=True)
    elif args.require_success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
