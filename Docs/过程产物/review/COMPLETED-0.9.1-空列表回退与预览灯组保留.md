# 0.9.1 空列表回退与预览灯组保留验证

- 日期：2026-11-06
- 版本：0.9.1
- 目标：All Cameras 关闭且列表为空时回退全部相机；选择配对行不隐藏其他灯组
- 本地 Blender：4.0.2（build `9be62e85`）；4.2.22 LTS 验证 4.2.0 Extension
- 结论：功能、4.0.2/4.2 安装态、五包构建和发布门面通过；4.5/5.2 未在本机安装验证

## 功能验收

- 空 Camera Environments 列表 + All Cameras 关闭：使用场景现有环境渲染全部相机；`RenderInfo.all_cameras=true`，两台相机均无 `environment`。
- 非空列表：只渲染已指定 Camera；原有单相机范围和空环境配对行为保持。
- 预览选中配对：选中 Camera/World/灯组生效，其他灯组 Collection 的 `hide_render` / `hide_viewport` / LayerCollection `exclude` 保持点击前状态。
- 渲染阶段：`switch_light_collections` 默认 `hide_others=True`，已登记灯组仍按配对隔离；`run_environment_pair_acceptance.py` 红/蓝图像差异通过。
- 成功、失败、取消后的状态恢复、隐藏工作目录和输出覆盖语义不变。

## 自动化结果

| 检查 | 结果 |
|---|---|
| `python -m unittest discover -s tests/unit -v` | 68/68 通过 |
| `python -m unittest discover -s tests/architecture -v` | 7/7 通过 |
| `uvx ruff check camera_batch_renderer tests scripts` | 通过 |
| Blender 4.0.2 `scripts/run_blender_tests.py` | `BLENDER_TESTS_OK` |
| Blender 4.0.2 `scripts/run_environment_pair_acceptance.py` | `ENVIRONMENT_PAIR_ACCEPTANCE_OK` |
| 4.0.2 Legacy 安装态 `scripts/test_legacy_install.py` | `INSTALLED_DEMO_OK`、`LEGACY_INSTALL_TEST_OK` |
| 4.2.22 上的 4.2.0 Extension 安装态 `scripts/run_installed_demo.py` | `INSTALLED_DEMO_OK` |
| `python scripts/release_gate.py --packages-only` | 五目标通过，`version=0.9.1` |
| `python scripts/release_gate.py --prerelease` | README/清单/版本面通过 |

## 安装包 SHA-256

| 文件 | SHA-256 |
|---|---|
| `RenderAllCameras-0.9.1-blender-4.0.2.zip` | `7ED850C9FE7B09E9735431FDF77F9416384019A88101CB05DC070D32C053F30C` |
| `RenderAllCameras-0.9.1-blender-4.1.1.zip` | `7F9307CC1C98DE7A2B8197126D6CFB206D61AF718A401C48AD9BA53A6EEE9A9D` |
| `RenderAllCameras-0.9.1-blender-4.2.0.zip` | `95428DAB98D4890C99F2DDE32587D280B924D10659D3F5388CDD95B36191E863` |
| `RenderAllCameras-0.9.1-blender-4.5-lts.zip` | `DF7E337C9193931E656F4B33323D57D2173B25A11CD3922B2DF60EB2AFD0AC1E` |
| `RenderAllCameras-0.9.1-blender-5.2-lts.zip` | `F4282F43F58391ABA00A64598FA1F57DF0393A1C9D7D55519BEA3DF07E78618A` |

## 未覆盖

- 4.5.13 LTS、5.2.1 LTS 本机没有对应 Blender，安装包只通过构建与内容门禁。
- 未执行完整五目标 GUI 发布套件；0.8.0 的原生退出/崩溃限制仍按历史记录保留。
- 未手动点击 GUI 截图；预览行为由单元测试和 4.0.2 后台集成测试覆盖。
