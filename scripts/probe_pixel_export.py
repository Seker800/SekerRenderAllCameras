"""Measure post-render image work without involving a GPU render or user Scene."""

from __future__ import annotations

import json
import os
import sys
import time
import tracemalloc
from pathlib import Path

import bpy
import numpy as np
import OpenImageIO as oiio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from blender_test_safety import require_isolated_profile  # noqa: E402

require_isolated_profile()
sys.path.insert(0, os.environ.get("RAC_PACKAGE_PARENT", str(ROOT)))
from camera_batch_renderer.blender.auxiliary import (  # noqa: E402
    _linear_to_byte,
    read_png_colors,
    save_file_alpha,
)

output = Path(os.environ["RAC_EXIT_OUTPUT"])
size = int(os.environ.get("RAC_PIXEL_SIZE", "1024"))
pixels = np.empty((size, size, 4), dtype=np.uint8)
values = np.arange(size, dtype=np.uint32) % 256
pixels[:, :, 0] = values
pixels[:, :, 1] = 255 - values
pixels[:, :, 2] = (values * 3) % 256
pixels[:, :, 3] = values
source = output / "source.png"
writer = oiio.ImageOutput.create(str(source))
assert writer.open(str(source), oiio.ImageSpec(size, size, 4, oiio.UINT8))
assert writer.write_image(pixels)
assert writer.close()
reference = bpy.data.images.load(str(source), check_existing=False)
try:
    row = reference.pixels[: size * 4]
    expected = {
        tuple(_linear_to_byte(row[index + channel]) for channel in range(3))
        for index in range(0, len(row), 4)
    }
finally:
    bpy.data.images.remove(reference)
measurements = {}
for name, call in (
    ("palette", lambda: read_png_colors(source)),
    ("alpha", lambda: save_file_alpha(source, output / "alpha.png")),
):
    tracemalloc.start()
    started = time.perf_counter()
    result = call()
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if name == "palette":
        assert result == expected, "Palette differs from scalar reference"
    measurements[name] = {"seconds": round(elapsed, 4), "python_peak_bytes": peak}
image_input = oiio.ImageInput.open(str(output / "alpha.png"))
try:
    alpha = image_input.read_image(format=oiio.UINT8).reshape(size, size)
    assert np.array_equal(alpha, pixels[:, :, 3])
finally:
    image_input.close()
report = {"version": bpy.app.version_string, "size": size, "measurements": measurements}
(output / "before-exit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("PIXEL_EXPORT_PROBE_OK", json.dumps(report), flush=True)
