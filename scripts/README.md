# Scripts

存放可复现的测试、打包和本地开发入口。脚本必须支持非交互执行、正确退出码和明确工作目录；不得写入用户 Blender 配置、安装/升级 MCP 或覆盖 `.blend`，除非脚本名称和文档明确说明且由用户主动执行。

- `build_extension.ps1`：使用 4.2+ Blender 校验并构建 Extension ZIP，同时从同一源码构建 4.0.2–4.1 Legacy Add-on ZIP。
- `build_legacy_package.py`：按固定顺序、时间戳和文件属性生成可重复构建的 Legacy ZIP。
- `run_blender_tests.py`：在目标 Blender 中验证真实渲染、像素、取消、故障与恢复。
- `test_legacy_install.py`：在隔离的 Blender 用户脚本目录中验证 Legacy 包安装、启用、面板、禁用与清理。
- `run_installed_demo.py`：针对已安装 Extension 运行演示场景端到端验收。
