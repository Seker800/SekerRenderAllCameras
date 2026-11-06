# 0.9.2 预览仅切换相机与 World 验证

- 日期：2026-11-06
- 版本：0.9.2
- 目标：点击 Camera Environments 列表中的已配置相机时，不显示选中灯组、不改任何灯组集合
- 本地 Blender：4.0.2（build `9be62e85`）；4.2.22 LTS 验证 4.2.0 Extension
- 结论：功能、4.0.2/4.2 安装态、五包构建和发布门面通过；4.5/5.2 未在本机安装验证

## 功能验收

- `preview_environment` 只设置 `scene.camera` 和 `scene.world`，不调用 `switch_light_collections`。
- 点击/修改配对行前后，所有 Collection 的 `hide_render` / `hide_viewport` 与所有 LayerCollection 的 `exclude` 完全一致；选中灯组也不会被显示。
- 渲染阶段仍按配对隔离已登记灯组，`run_environment_pair_acceptance.py` 红/蓝图像差异通过。
- All Cameras 空列表回退、激活相机/World 恢复、工作目录和输出覆盖语义不变。

## 自动化结果

| 检查 | 结果 |
|---|---|
| `python -m unittest discover -s tests/unit` | 68/68 通过 |
| `python -m unittest discover -s tests/architecture` | 7/7 通过 |
| Ruff | 通过 |
| Blender 4.0.2 `scripts/run_blender_tests.py` | `BLENDER_TESTS_OK` |
| Blender 4.0.2 `scripts/run_collection_visibility_tests.py` | `COLLECTION_VISIBILITY_TESTS_OK` |
| 4.0.2 Legacy 安装态 `scripts/test_legacy_install.py` | `INSTALLED_DEMO_OK`、`LEGACY_INSTALL_TEST_OK` |
| 4.2.22 上的 4.2.0 Extension 安装态 | `INSTALLED_DEMO_OK` |
| `python scripts/release_gate.py --packages-only` | 五目标通过，`version=0.9.2` |
| `python scripts/release_gate.py --prerelease` | README/清单/版本面通过 |

## 安装包 SHA-256

| 文件 | SHA-256 |
|---|---|
| `RenderAllCameras-0.9.2-blender-4.0.2.zip` | `CB21596BA95C4381A7E3E835458EB56ADC78285EC9CD45F64D96F8DDC2D94900` |
| `RenderAllCameras-0.9.2-blender-4.1.1.zip` | `31863B9A0A43571D1D9713F4E76F43E786D8E3058A9E29C1E32DFAAB31E100B1` |
| `RenderAllCameras-0.9.2-blender-4.2.0.zip` | `978E477952D63E0412536BE28A40784D0E8D459E2BE79A8D623D315E180F733A` |
| `RenderAllCameras-0.9.2-blender-4.5-lts.zip` | `D89B20D3D81E5C9336435D1EFE3C125C1B32029E39BC980CC5D3BB26C17FD04B` |
| `RenderAllCameras-0.9.2-blender-5.2-lts.zip` | `5A1B2F2BBDC2EE47888CEBD73A37AA538001E1E3C176008F2E1776F06DB73294` |

## 未覆盖

- 4.5.13 LTS、5.2.1 LTS 本机没有对应 Blender，安装包只通过构建与内容门禁。
- 未执行完整五目标 GUI 发布套件；0.8.0 的原生退出/崩溃限制仍按历史记录保留。
- 未手动点击 GUI 截图；预览不改集合由单元测试、集成测试和集合专项测试覆盖。
