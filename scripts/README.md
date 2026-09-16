# Scripts

`run_gui_render_tests.py` 从“新渲染窗口”用户偏好启动真实 GUI 三摄影机批次，并主动移除
`render_complete` handler，验证渲染启动期间的弹窗抑制、输出文件后备信号推进、当前图片后停止和用户偏好不变。

存放可复现的测试、打包和本地开发入口。脚本必须支持非交互执行、正确退出码和明确工作目录；不得写入用户 Blender 配置、安装/升级 MCP 或覆盖 `.blend`，除非脚本名称和文档明确说明且由用户主动执行。

- `build_extension.ps1`：使用 4.2+ Blender 校验并构建 Extension ZIP，同时从同一源码构建 4.0.2–4.1 Legacy Add-on ZIP。
- `build_legacy_package.py`：按固定顺序、时间戳和文件属性生成可重复构建的 Legacy ZIP。
- `run_blender_tests.py`：在目标 Blender 中验证真实渲染、像素、取消、故障与恢复。
- `test_legacy_install.py`：在隔离的 Blender 用户脚本目录中验证 Legacy 包安装、启用、面板、禁用与清理。
- `run_installed_demo.py`：针对已安装 Extension 运行演示场景端到端验收。
- `run_environment_pair_acceptance.py`：创建两 Camera、两套隐藏/排除灯组与两个 World 的 EEVEE 真实场景，实际导出 Beauty，检查图片色彩、RenderInfo 和宿主状态恢复。验收产物保留在 `build/environment-pair-acceptance/`。
- `run_material_id_acceptance.py`：创建双材质面与未分配材质物体，实际导出 Material ID PNG，逐像素核对黑色背景、稳定颜色映射、材质槽/面分配不变和临时数据清理。验收产物保留在 `build/material-id-acceptance/`。
- `capture_plugin_screenshot.py`：在真实 Blender GUI 中加载已安装插件、展开 3D View 的插件侧栏并截取编辑器区域；通过 `RAC_SCREENSHOT_PATH` 指定临时截图位置，不保存 `.blend`。
- `release_gate.py`：比较 Extension/Legacy ZIP 的功能文件并检查所有发布版本与下载链接；Release 上传后加 `--verify-online` 验证两个线上资产。
