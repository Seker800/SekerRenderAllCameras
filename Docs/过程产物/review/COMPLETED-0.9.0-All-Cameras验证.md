# 0.9.0 All Cameras 验证记录

- 日期：2026-11-06
- 版本：0.9.0
- 目标：新增 All Cameras 相机范围开关，并构建五目标安装包
- 本地 Blender：4.0.2（build `9be62e85`）；另用 4.2.22 LTS 验证 4.2.0 Extension
- 结论：新功能、安装态、五包构建与发布门禁通过；4.5/5.2 未在本机安装验证

## 功能验收

- 默认 `include_all_cameras=True`，两个面板均绘制 **All Cameras**，运行中禁用。
- 关闭后只渲染 Camera Environments 中指定 Camera；配对行灯组和 World 都为空时仍选中该 Camera，并使用场景默认环境。
- 空 Camera Environments 列表在创建隐藏工作目录或任何图片前抛出 `ValueError`；空行（Camera 未指定）同样不会选中任何相机。
- 全量批次和单相机范围批次的 `RenderInfo.json` 分别记录 `all_cameras=true/false` 与正确 `camera_count`。
- 成功、失败、取消后 Camera、World、集合可见性、渲染路径和帧状态恢复不变；临时 Scene 与工作目录不残留。

## 自动化结果

| 检查 | 结果 |
|---|---|
| `python -m unittest discover -s tests/unit -v` | 68/68 通过 |
| `python -m unittest discover -s tests/architecture -v` | 7/7 通过 |
| `uvx ruff check camera_batch_renderer tests scripts` | 通过 |
| Blender 4.0.2 `scripts/run_blender_tests.py` | 通过，包含范围开关和空列表断言 |
| 4.0.2 Legacy 安装态 `scripts/test_legacy_install.py` | `INSTALLED_DEMO_OK`、`LEGACY_INSTALL_TEST_OK` |
| 4.2.22 上的 4.2.0 Extension 安装态 `scripts/run_installed_demo.py` | `INSTALLED_DEMO_OK` |
| 4.2 Extension `--command extension validate` | 通过 |
| `python scripts/release_gate.py --packages-only` | 五目标通过，`version=0.9.0` |
| `python scripts/release_gate.py --prerelease` | README/清单/版本面通过 |

## 安装包 SHA-256

| 文件 | SHA-256 |
|---|---|
| `RenderAllCameras-0.9.0-blender-4.0.2.zip` | `97C9AC38DE7109F359FA3B89984E0755732233686721283B2C267D3081C6DB4B` |
| `RenderAllCameras-0.9.0-blender-4.1.1.zip` | `82C000FA15B12E7BEF256C98E8DD2233091E733A695F5B61B26797370C8E0F30` |
| `RenderAllCameras-0.9.0-blender-4.2.0.zip` | `211BDBFD1A138C79BD7B1962651BBD9EC6640D2A912FAB3958C8CE3D9C1E4FD7` |
| `RenderAllCameras-0.9.0-blender-4.5-lts.zip` | `1D29DF212A5AAD08CDD71F5181837E9AB3BC5BC93FC7C13BD88F4CA173B61D1D` |
| `RenderAllCameras-0.9.0-blender-5.2-lts.zip` | `94028C2F9C0F06A1F76EE382576503C79AF1702AF56240E42B6E7BA9D458D7E7` |

## 未覆盖

- 4.5.13 LTS、5.2.1 LTS 本机没有对应 Blender，安装包只通过构建与内容门禁，未做安装态渲染。
- 未执行 0.8.0 的完整五目标发布套件；0.8.0 的原生 GUI 退出/崩溃限制仍按历史记录保留。
- 本次未手动点击 GUI 截图；面板绘制由安装态 LayoutRecorder 断言和 4.0.2 后台集成测试覆盖。
