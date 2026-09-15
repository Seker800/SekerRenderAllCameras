# Render All Cameras for Blender

**One-click batch rendering for every camera in a Blender scene.** Render still images with
automatic filenames, optional alpha masks, Object ID maps, and JSON manifests.

一键逐个渲染 Blender 当前场景中的全部摄影机，并自动输出规范命名的静帧、Alpha、Object ID
和 JSON 清单。

[![Download Blender Extension](https://img.shields.io/badge/Download-Extension_4.2+-F5792A?style=for-the-badge&logo=blender&logoColor=white)](https://github.com/Seker800/SekerRenderAllCameras/releases/latest/download/camera_batch_renderer-0.2.0.zip)
[![Download Legacy Add-on](https://img.shields.io/badge/Download-Legacy_4.0.2%E2%80%934.1-555555?style=for-the-badge&logo=blender&logoColor=white)](https://github.com/Seker800/SekerRenderAllCameras/releases/latest/download/camera_batch_renderer-0.2.0-legacy.zip)

[![Latest release](https://img.shields.io/github/v/release/Seker800/SekerRenderAllCameras)](https://github.com/Seker800/SekerRenderAllCameras/releases/latest)
[![Blender 4.0.2+](https://img.shields.io/badge/Blender-4.0.2%2B-F5792A?logo=blender&logoColor=white)](#compatibility)
[![License: GPL v3+](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](LICENSE)

> **[Download the latest ready-to-install ZIP](https://github.com/Seker800/SekerRenderAllCameras/releases/latest/download/camera_batch_renderer-0.1.1.zip)** — do not unzip it.

## Why use it?

- Render every camera in the current Scene with one click—built for still images, not animation.
- Keep the current Blender render settings for Beauty output.
- Add an optional lossless grayscale Alpha mask for each camera.
- Add an optional exact-color Object ID map plus a machine-readable color mapping JSON.
- Name files from the batch prefix, `.blend` file, camera, channel, resolution, and render engine.
- Allocate `001`, `002`, … batch folders safely without overwriting existing work.
- Track progress, cancel cooperatively, record failures, and restore the active camera and settings.

Example filenames:

```text
001_ProductShot_Camera_Front_Beauty_1920x1080_Cycles.png
001_ProductShot_Camera_Front_Alpha_1920x1080.png
001_ProductShot_Camera_Front_ObjectID_1920x1080_Object.png
001_ProductShot_RenderInfo.json
001_ProductShot_ObjectID.json
```

## Install

### Blender 4.2 or newer

1. **[Download `camera_batch_renderer-0.2.0.zip`](https://github.com/Seker800/SekerRenderAllCameras/releases/latest/download/camera_batch_renderer-0.2.0.zip)**.
2. In Blender, open **Edit → Preferences → Get Extensions**.
3. Open the top-right menu and choose **Install from Disk**.
4. Select the downloaded ZIP. Do not extract it first.

### Blender 4.0.2–4.1

1. **[Download `camera_batch_renderer-0.2.0-legacy.zip`](https://github.com/Seker800/SekerRenderAllCameras/releases/latest/download/camera_batch_renderer-0.2.0-legacy.zip)**.
2. In Blender, open **Edit → Preferences → Add-ons**.
3. Click **Install…**, choose the downloaded ZIP, then enable **Render: Render All Cameras**.

## Quick start

1. Save the `.blend` file—the output location is based on it.
2. Put the mouse over the 3D Viewport and press <kbd>N</kbd>.
3. Open **Batch Render → Render All Cameras**.
4. Choose the starting batch number and enable Alpha and/or Object ID if needed.
5. Click **Render All Cameras**.

The same controls are also available under **Output Properties → Render All Cameras**. Results are
written next to the `.blend` file:

```text
MyProject/
├─ ProductShot.blend
└─ RenderOutput/
   └─ 001/
      ├─ ...Beauty....png
      ├─ ...Alpha....png
      ├─ ...ObjectID....png
      ├─ ...RenderInfo.json
      └─ ...ObjectID.json
```

中文快速使用：Blender 4.2+ 下载 Extension 包并选择“从磁盘安装”；Blender 4.0.2–4.1
下载 Legacy 包并从“插件”页安装。不要解压 ZIP。保存 `.blend` 后，将鼠标放到 3D 视图并按
<kbd>N</kbd>，进入 **Batch Render** 标签即可开始批量渲染。

## Demo

Open [`examples/RenderAllCameras_Demo.blend`](examples/RenderAllCameras_Demo.blend) to try a small
two-camera acceptance scene. A complete run produces two Beauty images, two Alpha images, two
Object ID images, `RenderInfo.json`, and `ObjectID.json`.

## Compatibility

| Environment | Status |
| --- | --- |
| Blender 4.0.2 | Tested; minimum supported version |
| Blender 4.1.1 | Tested |
| Blender 4.2.0 | Tested; first Extension version |
| Blender 4.5.11 LTS | Tested |
| Blender 5.2.1 LTS | Tested |
| Blender 4.0.0–4.0.1 and earlier | Not supported |
| Cycles, EEVEE, Workbench | Beauty and auxiliary channels supported |
| Third-party render engines | Beauty only by default |

No maximum Blender version is declared. New Blender releases are intended to remain supported, but
the tested versions above are the release gates. Blender 4.0.2–4.1 use the Legacy package because
the official Extensions system begins with Blender 4.2.

Object ID does not currently include Volume objects. Animation, Material ID, Cryptomatte,
Multiview, multi-Scene queues, and distributed rendering are outside the first release.

## Development and tests

```powershell
python -m unittest discover -s tests/unit -v
python -m unittest discover -s tests/architecture -v
uvx ruff check camera_batch_renderer tests scripts
blender --background --factory-startup --python scripts/run_blender_tests.py
powershell -ExecutionPolicy Bypass -File scripts/build_extension.ps1
```

The test suite covers naming, natural camera order, atomic batch allocation and manifests, state
restoration, cancellation, handled failures, Alpha/Object ID pixels, Blender 4.0.2/4.1/4.2/4.5/5.2
integration, both package formats, installed-package rendering, and UI registration.

Architecture and implementation documentation lives in [`Docs/`](Docs/README.md). The original
product scope is recorded in [`PLAN.md`](PLAN.md).

## License

Copyright © 2026 Seker800. Released under
[`GPL-3.0-or-later`](LICENSE), consistent with the Extension manifest.

<!-- Search terms: Blender addon, Blender extension, batch render all cameras, multi-camera render,
still image renderer, alpha mask, object ID map, render automation, Python bpy. -->
