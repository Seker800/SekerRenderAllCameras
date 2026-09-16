# Scripts

`run_gui_render_tests.py` 从“新渲染窗口”用户偏好、真实 3D View 上下文启动 GUI 三摄影机批次，
验证弹窗抑制、完整 handler 信号推进、当前图片后停止、连续运行和用户偏好不变；
丢失 `render_complete` 的文件后备语义由纯逻辑测试单独覆盖。

存放可复现的测试、打包和本地开发入口。脚本必须支持非交互执行、正确退出码和明确工作目录；不得写入用户 Blender 配置、安装/升级 MCP 或覆盖 `.blend`，除非脚本名称和文档明确说明且由用户主动执行。

- `build_extension.ps1`：读取 `packaging/blender_targets.json`，从共享纯核心装配 4.0.2、4.1.1、4.2.0、4.5 LTS、5.2 LTS 五个独立 ZIP，并用各目标 Blender 校验 Extension 清单。
- `build_legacy_package.py`：按固定顺序、时间戳和文件属性生成可重复构建的 Legacy ZIP。
- `run_blender_tests.py`：在目标 Blender 中验证真实渲染、像素、取消、故障与恢复。
- `run_blender_edge_cases.py`：验证预检、Camera/格式矩阵、Compositor、Render Border/Crop、文件名冲突与 `.blend` 不被保存。
- `run_full_test_suite.ps1`：全量测试唯一入口；执行所有层、隔离安装/卸载并生成 `build/test-reports/` JSON 摘要和逐步日志。
- `test_legacy_install.py`：在 factory-startup 隔离环境中安装 Legacy 包，并从真实安装路径运行完整四通道演示后禁用与清理。
- `run_installed_demo.py`：针对已安装 Legacy/Extension 运行演示场景端到端验收并输出跨版本功能契约。
- `run_stress_smoke.py`：执行 50 Camera 和连续十批小尺寸真实渲染烟测，检查输出稳定性与临时数据清理。
- `test_target_version_rejection.py`：在真实目标 Blender 中确认错版本包的固定宿主策略拒绝注册。
- `verify_cross_version_contracts.py`：比较五个安装态包的 Camera、通道、结果矩阵、清单 schema 与 ID 调色板。
- `run_environment_pair_acceptance.py`：创建两 Camera、两套隐藏/排除灯组与两个 World 的 EEVEE 真实场景，实际导出 Beauty，检查图片色彩、RenderInfo 和宿主状态恢复。验收产物保留在 `build/environment-pair-acceptance/`。
- `run_material_id_acceptance.py`：创建双材质面与未分配材质物体，实际导出 Material ID PNG，逐像素核对黑色背景、稳定颜色映射、材质槽/面分配不变和临时数据清理。验收产物保留在 `build/material-id-acceptance/`。
- `run_gui_host_control.py`：在加载插件但不启动插件批次的前提下执行单张异步 GUI 渲染，用于区分 Blender/驱动宿主崩溃与插件批次调度故障；它不是插件 GUI 验收的替代品。
- `capture_plugin_screenshot.py`：在真实 Blender GUI 中加载已安装插件、展开 3D View 的插件侧栏并截取编辑器区域；通过 `RAC_SCREENSHOT_PATH` 指定临时截图位置，不保存 `.blend`。
- `release_gate.py`：比较五个 ZIP 的共享功能文件并检查版本与下载链接；Release 上传后加 `--verify-online` 下载五个线上资产并核对本地 SHA-256。
